from neo4j import GraphDatabase
import Configuration


class DiaFunc:
    # This class is the main object that all heuristics will work with.
    # This class has 2 main functions:
    #   1. obtain (from a neo4j DB) and represent all relevant information regarding a function, in order to allow
    #      efficient similarity testing.
    #   2. Populate a neo4j DB function object with a special node (node label: "DiaFuncInfo", relationship type: "Dia")
    #      that holds the information needed for future uses of this class.

    def __init__(self, driver, func_uuid: str, usage: str):
        """
        :param driver: neo4j DB bolt driver object, used for communicating with the relevant DB
        :param func_uuid: (STR) the UUID of the function node in the neo4j DB
        :param usage: (STR) Does this object 'Obtain' info from the DB, or 'Populate' the DB with new info
        """
        self.driver = driver
        self.func_uuid = func_uuid
        self.edge_count = 0
        self.basic_block_count = 0
        self.instruction_count = 0
        self.clobbered_registers = []
        self.cyclomatic_complexity = 0
        self.symbol_list = []
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

    def obtain(self):
        pass

    def populate(self):
        # Create a special node (node label: "DiaFuncInfo", relationship type: "Dia") that holds the information
        # needed for future uses of this class.
        # Connect this node to the actual Function node (MLIL Function) that it represents
        with self.driver.session() as session:
            # Get information from the function node properties
            node_properties = session.run("MATCH (f:Function {UUID: '" + self.func_uuid + "'}) return properties(f)")
            node_properties = node_properties.peek()[0]
            self.calling_convention = node_properties['CallingConvention']
            self.clobbered_registers = node_properties['ClobberedRegisters']
            self.hash = node_properties['HASH']

            # Get information regarding the context and surrounding of the function and its inhabitants
            test = session.run("MATCH (:BasicBlock)-[r:Branch {ParentFunctionUUID: \"" + self.func_uuid +
                               "\"}]->(end:BasicBlock) " 
                               "RETURN count(DISTINCT(end)) as vertices_count, count(DISTINCT(r)) as edges_count ")
            self.edge_count = test.peek()['edges_count']
            self.basic_block_count = test.peek()['vertices_count']
            populate_symbol_list()




if __name__ == "__main__":
    driver = GraphDatabase.driver(Configuration.uri, auth=(Configuration.user, Configuration.password),
                                  max_connection_lifetime=60, max_connection_pool_size=1000,
                                  connection_acquisition_timeout=30)
    df = DiaFunc(driver, '49efb0bc-6884-438a-9523-f76fc63e7d17', 'Populate')
    print("stop")

