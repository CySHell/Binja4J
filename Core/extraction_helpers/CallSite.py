from binaryninja import *
import xxhash


################################################################################################################
#                                       CallSite                                                               #
################################################################################################################

class Neo4jCallSite:

    def __init__(self, context):
        self.context = context

    def serialize(self):
        csv_template = {
            'mandatory_node_dict': {
                # stub, this class represents only a relationship
            },
            'mandatory_relationship_dict': {
                'START_ID': self.context.ParentHASH,
                'END_ID': self.context.SelfHASH,
                'TYPE': 'FunctionCall',
                'StartNodeLabel': 'Instruction',
                'EndNodeLabel': 'Function',
            },

            'mandatory_context_dict': self.context.get_context(),

            'node_attributes': {
                # stub, this class represents only a relationship
            },
            'relationship_attributes': {

            },
        }

        return csv_template
