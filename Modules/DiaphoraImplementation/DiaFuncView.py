from neo4j import GraphDatabase
import Configuration


class DiaFunc:
    # This class is the export_bv object that all heuristics will work with.
    # This class has 2 export_bv functions:
    #   1. obtain (from a neo4j DB) and represent all relevant information regarding a RootFunction, in order to allow
    #      efficient similarity testing.
    #   2. Populate a neo4j DB RootFunction object with a special node (node label: "DiaFuncInfo", relationship type: "Dia")
    #      that holds the information needed for future uses of this class.

    def __init__(self, driver, func_uuid: str, usage: str):
        """
        :param driver: neo4j DB bolt driver object, used for communicating with the relevant DB
        :param func_uuid: (STR) the UUID of the RootFunction node in the neo4j DB
        :param usage: (STR) Does this object 'Obtain' info from the DB, or 'Populate' the DB with new info
        """
        self.driver = driver
        self.func_uuid = func_uuid
        self.edge_count = 0
        self.basic_block_count = 0
        self.instruction_count = 0
        self.clobbered_registers = []
        self.cyclomatic_complexity = 0
        self.func_strings = self.populate_strings()
        self.symbol_list = self.populate_symbols()
        self.hash = ''
        self.fuzzy_hash = {
            'SSDEEP': None,
        }
        self.calling_convention = ''

        if usage is 'Obtain':
            self.usage = usage
            self.obtain()
        else:
            if usage is 'Populate':
                self.usage = usage
                self.populate()
            else:
                print('Error initializing DiaFunc object, bad usage string given: ', usage)

        print(self.func_strings)

    def obtain(self):
        pass

    def populate(self):
        # Create a special node (node label: "DiaFuncInfo", relationship type: "Dia") that holds the information
        # needed for future uses of this class.
        # Connect this node to the actual Function node (MLIL Function) that it represents
        with self.driver.session() as session:
            # Get information from the RootFunction node properties
            self.populate_from_node_properties()

            # Get information regarding the graph structure of the RootFunction
            self.populate_graph_related_attributes()

            # Get all symbols from this RootFunction
            self.populate_strings()

            self.populate_symbols()

            print("stop")

    def populate_from_node_properties(self):
        with self.driver.session() as session:
            # Get information from the RootFunction node properties
            node_properties = session.run("MATCH (f:Function {UUID: '" + self.func_uuid + "'}) return properties(f)")
            node_properties = node_properties.peek()[0]
            self.calling_convention = node_properties['CallingConvention']
            self.clobbered_registers = node_properties['ClobberedRegisters']
            self.hash = node_properties['HASH']

    def populate_graph_related_attributes(self):
        with self.driver.session() as session:
            # Get information regarding the graph structure of the RootFunction
            test = session.run("MATCH (:BasicBlock)-[r:Branch {ParentFunctionUUID: \"" + self.func_uuid +
                               "\"}]->(end:BasicBlock) "
                               "RETURN count(DISTINCT(end)) as vertices_count, count(DISTINCT(r)) as edges_count ")
            self.edge_count = test.peek()['edges_count']
            self.basic_block_count = test.peek()['vertices_count']

    def populate_strings(self):
        string_dict = {}
        with self.driver.session() as session:
            string_list = session.run("MATCH ()-[:MemberBB|:Branch {ParentFunctionUUID: \'" +
                                      self.func_uuid + "\'}]->(bb:BasicBlock) "
                                                       "WITH collect(bb) as bb_list "
                                                       "UNWIND bb_list as basicBlock "
                                                       "MATCH ()-[:InstructionChain|:NextInstruction "
                                                       "{ParentBB: basicBlock.UUID}]->(RootInstruction:Instruction) "
                                                       "WITH collect(RootInstruction) as instruction_list "
                                                       "UNWIND instruction_list as instr "
                                                       "MATCH (instr)-[:Operand*1..3]-(exp:Expression) "
                                                       "WITH collect(exp) as expression_list "
                                                       "UNWIND expression_list as RootExpression "
                                                       "MATCH (RootExpression)-[:ConstantOperand]->(const:Constant) "
                                                       "WITH collect(const) as constant_list "
                                                       "MATCH (bv:BinaryView)-[:MemberFunc]->"
                                                       "                      (:Function {UUID: \'" + self.func_uuid + "\'})"
                                                       "UNWIND constant_list as constant "
                                                       "MATCH (constant)-[:StringRef]->(string:String) "
                                                       "MATCH (:Constant)-[:StringRef {BinaryViewUUID: bv.UUID}]->(string)"
                                                       "RETURN collect(string) as strList").single().value()

            # Each string is a String Neo4j node object within the current RootFunction
            for string in string_list:
                string_dict.update({string['HASH']: string['RawData']})

            return string_dict

    def populate_symbols(self):
        symbol_dict = {}
        with self.driver.session() as session:
            symbol_list = session.run("MATCH ()-[:MemberBB|:Branch {ParentFunctionUUID: \'" +
                                      self.func_uuid + "\'}]->(bb:BasicBlock) "
                                                       "WITH collect(bb) as bb_list "
                                                       "UNWIND bb_list as basicBlock "
                                                       "MATCH ()-[:InstructionChain|:NextInstruction "
                                                       "{ParentBB: basicBlock.UUID}]->(RootInstruction:Instruction) "
                                                       "WITH collect(RootInstruction) as instruction_list "
                                                       "UNWIND instruction_list as instr "
                                                       "MATCH (instr)-[:Operand*1..3]-(exp:Expression) "
                                                       "WITH collect(exp) as expression_list "
                                                       "UNWIND expression_list as RootExpression "
                                                       "MATCH (RootExpression)-[:ConstantOperand]->(const:Constant) "
                                                       "WITH collect(const) as constant_list "
                                                       "MATCH (bv:BinaryView)-[:MemberFunc]->"
                                                       "                      (:Function {UUID: \'" + self.func_uuid + "\'})"
                                                       "UNWIND constant_list as constant "
                                                       "MATCH (constant)-[:SymbolRef]->(symbol:Symbol) "
                                                       "MATCH (:Constant)-[:SymbolRef {BinaryViewUUID: bv.UUID}]->(symbol)"
                                                       "RETURN collect(symbol) as symbolList").single().value()

            # Each symbol is a Symbol Neo4j node object within the current RootFunction
            for symbol in symbol_list:
                symbol_dict.update({symbol['HASH']: symbol['SymbolName']})

            return symbol_dict


if __name__ == "__main__":
    driver = GraphDatabase.driver(Configuration.analysis_database_uri, auth=(Configuration.analysis_database_user, Configuration.analysis_database_password),
                                  max_connection_lifetime=60, max_connection_pool_size=1000,
                                  connection_acquisition_timeout=30)
    df = DiaFunc(driver, 'fb1a0415-cb75-46c3-bb43-39055ec8c370', 'Populate')
    print("stop")
