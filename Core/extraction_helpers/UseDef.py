from binaryninja import *


################################################################################################################
#                                       UseDef chain                                                           #
################################################################################################################

class Neo4jUseDef:

    def __init__(self, context, type: str):
        self.context = context
        self.type = type

    def serialize(self):
        csv_template = {
            'mandatory_node_dict': {
                # stub, this class represents only a relationship
            },
            'mandatory_relationship_dict': {
                'START_ID': self.context.ParentHASH,
                'END_ID': self.context.SelfHASH,
                'TYPE': self.type,
                'StartNodeLabel': 'Variable',
                'EndNodeLabel': 'Instruction',
            },

            'mandatory_context_dict': self.context.get_context(),

            'node_attributes': {
                # stub, this class represents only a relationship
            },
            'relationship_attributes': {

            },
        }

        return csv_template
