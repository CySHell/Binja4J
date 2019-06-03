from binaryninja import *


################################################################################################################
#                                       UseDef chain                                                           #
################################################################################################################

class Neo4jUseDef:

    def __init__(self, variable_node_uuid, instruction_node_uuid, root_binary_view_uuid, type: str):
        self.variable_uuid = variable_node_uuid
        self.instruction_uuid = instruction_node_uuid
        self.root_binary_view_uuid = root_binary_view_uuid
        self.type = type

    def serialize(self):
        csv_template = {
            'mandatory_node_dict': {
                # stub, this class represents only a relationship
            },
            'mandatory_relationship_dict': {
                'START_ID': self.variable_uuid,
                'END_ID': self.instruction_uuid,
                'TYPE': self.type,
                'StartNodeLabel': 'Variable',
                'EndNodeLabel': 'Instruction',
                'BinaryView': self.root_binary_view_uuid,
            },

            'mandatory_context_dict': {

            },

            'node_attributes': {
                # stub, this class represents only a relationship
            },
            'relationship_attributes': {

            },
        }

        return csv_template
