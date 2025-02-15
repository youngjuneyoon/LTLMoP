""" 
    ===============================================
    createJTLVinput.py - LTL Pre-Processor Routines
    ===============================================
    
    Module that creates the input files for the JTLV based synthesis algorithm.
    Its functions create the skeleton .smv file and the .ltl file which
    includes the topological relations and the given spec.
"""
import math
import parseEnglishToLTL
import textwrap
from LTLParser.LTLFormula import LTLFormula, LTLFormulaType, treeToString

def createSMVfile(fileName, sensorList, robotPropList):
    ''' This function writes the skeleton SMV file.
    It takes as input a filename, the number of regions, the list of the
    sensor propositions and the list of robot propositions (without the regions).
    '''

    fileName = fileName + '.smv'
    smvFile = open(fileName, 'w')

    # Write the header
    smvFile.write(textwrap.dedent("""
    -- Skeleton SMV file
    -- (Generated by the LTLMoP toolkit)


    MODULE main
        VAR
            e : env();
            s : sys();
    """));

    # Define sensor propositions
    smvFile.write(textwrap.dedent("""
    MODULE env -- inputs
        VAR
    """));
    for sensor in sensorList:
        smvFile.write('\t\t')
        smvFile.write(sensor)
        smvFile.write(' : boolean;\n')

    smvFile.write(textwrap.dedent("""
    MODULE sys -- outputs
        VAR
    """));

    # Define robot propositions
    for robotProp in robotPropList:
        smvFile.write('\t\t')
        smvFile.write(robotProp)
        smvFile.write(' : boolean;\n')

    # close the file
    smvFile.close()
    

def createTopologyFragment(adjData, regions, use_bits=True):
    if use_bits:
        numBits = int(math.ceil(math.log(len(adjData),2)))
        # TODO: only calc bitencoding once
        bitEncode = parseEnglishToLTL.bitEncoding(len(adjData), numBits)
        currBitEnc = bitEncode['current']
        nextBitEnc = bitEncode['next']

    # The topological relation (adjacency)
    adjFormulas = []

    for Origin in range(len(adjData)):
        # from region i we can stay in region i
        adjFormula = '\t\t\t []( ('
        adjFormula = adjFormula + (currBitEnc[Origin] if use_bits else "s."+regions[Origin].name)
        adjFormula = adjFormula + ') -> ( ('
        adjFormula = adjFormula + (nextBitEnc[Origin] if use_bits else "next(s."+regions[Origin].name+")")
        adjFormula = adjFormula + ')'
        
        for dest in range(len(adjData)):
            if adjData[Origin][dest]:
                # not empty, hence there is a transition
                adjFormula = adjFormula + '\n\t\t\t\t\t\t\t\t\t| ('
                adjFormula = adjFormula + (nextBitEnc[dest] if use_bits else "next(s."+regions[dest].name+")")
                adjFormula = adjFormula + ') '

        # closing this region
        adjFormula = adjFormula + ' ) ) '

        adjFormulas.append(adjFormula)

    # In a BDD strategy, it's best to explicitly exclude these
    adjFormulas.append("[]"+createInitialRegionFragment(regions, use_bits))

    return " & \n".join(adjFormulas)

def createInitialRegionFragment(regions, use_bits=True):
    # Setting the system initial formula to allow only valid
    #  region (encoding). This may be redundant if an initial region is
    #  specified, but it is here to ensure the system cannot start from
    #  an invalid, or empty region (encoding).
    if use_bits:
        numBits = int(math.ceil(math.log(len(regions),2)))
        # TODO: only calc bitencoding once
        bitEncode = parseEnglishToLTL.bitEncoding(len(regions), numBits)
        currBitEnc = bitEncode['current']
        nextBitEnc = bitEncode['next']

        initreg_formula = '\t\t\t( ' + currBitEnc[0] + ' \n'
        for regionInd in range(1,len(currBitEnc)):
            initreg_formula = initreg_formula + '\t\t\t\t | ' + currBitEnc[regionInd] + '\n'
        initreg_formula = initreg_formula + '\t\t\t) \n'
    else:
        initreg_formula = "\n\t({})".format(" | ".join(["({})".format(" & ".join(["s."+r2.name if r is r2 else "!s."+r2.name for r2 in regions])) for r in regions]))
        
    return initreg_formula

def createNecessaryFillerSpec(spec_part):
    """ Both assumptions guarantees need to have at least one each of
        initial, safety, and liveness.  If any are not present,
        create trivial TRUE ones. """

    if spec_part.strip() == "":
        filler_spec = ["TRUE", "[](TRUE)", "[]<>(TRUE)"]
    else:
        formula = LTLFormula.fromString(spec_part)
        filler_spec = []
        if not formula.getConjunctsByType(LTLFormulaType.INITIAL):
            filler_spec.append("TRUE")
        if not formula.getConjunctsByType(LTLFormulaType.SAFETY):
            filler_spec.append("[](TRUE)")
        if not formula.getConjunctsByType(LTLFormulaType.LIVENESS):
            filler_spec.append("[]<>(TRUE)")

    return " & ".join(filler_spec) 

def flattenLTLFormulas(f):
    if isinstance(f, LTLFormula):
        return str(f)

    # If we've received a list of LTLFormula, assume that they should be conjoined
    if isinstance(f, list) and all((isinstance(sf, LTLFormula) for sf in f)):
        return " & \n".join([treeToString(sf.tree, top_level=False) for sf in f])

    if isinstance(f, basestring):
        return f

    raise ValueError("Invalid formula type: must be either string, LTLFormula, or LTLFormula list")

def createLTLfile(fileName, spec_env, spec_sys):
    ''' This function writes the LTL file. It encodes the specification and 
    topological relation. 
    It takes as input a filename, the list of the
    sensor propositions, the list of robot propositions (without the regions),
    the adjacency data (transition data structure) and
    a specification
    '''

    spec_env = flattenLTLFormulas(spec_env)
    spec_sys = flattenLTLFormulas(spec_sys)

    # Force .ltl suffix
    if not fileName.endswith('.ltl'):
        fileName = fileName + '.ltl'

    ltlFile = open(fileName, 'w')

    # Write the header and begining of the formula
    ltlFile.write(textwrap.dedent("""
    -- LTL specification file
    -- (Generated by the LTLMoP toolkit)

    """))
    ltlFile.write('LTLSPEC -- Assumptions\n')
    ltlFile.write('\t(\n')

    filler = createNecessaryFillerSpec(spec_env) 
    if filler: 
        ltlFile.write('\t' + filler)

    # Write the environment assumptions
    # from the 'spec' input 
    if spec_env.strip() != "":
        if filler:
            ltlFile.write('& \n')
        ltlFile.write(spec_env)
    ltlFile.write('\n\t);\n\n')

    ltlFile.write('LTLSPEC -- Guarantees\n')
    ltlFile.write('\t(\n')

    filler = createNecessaryFillerSpec(spec_sys) 
    if filler: 
        ltlFile.write('\t' + filler)

    # Write the desired robot behavior
    if spec_sys.strip() != "":
        if filler:
            ltlFile.write('& \n')
        ltlFile.write(spec_sys)

    # Close the LTL formula
    ltlFile.write('\n\t);\n')

    # close the file
    ltlFile.close()


