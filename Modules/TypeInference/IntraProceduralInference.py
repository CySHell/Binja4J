from ... import Configuration
from .Core.Common import Neo4jConnector

class InfereeVariable:
    # Representation of an MLIL_VAR with a type that is being propagated to its defining variables
    # This class interacts with the neo4j graph only, no interaction with the BinaryView itself is allowed.

    def __init__(self, inferee_uuid):
        self.original_uuid = inferee_uuid
        self.driver = Neo4jConnector.get_driver()
        self.def_chain = dict()
        self.use_chain = dict()



