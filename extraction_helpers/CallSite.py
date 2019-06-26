from binaryninja import *
import xxhash


################################################################################################################
#                                       CallSite                                                               #
################################################################################################################

class Neo4jCallSite:

    def __init__(self, callsite_instruction_node_uuid, called_function_node_uuid, context):
        self.callsite_instruction_node_uuid = callsite_instruction_node_uuid
        self.called_function_node_uuid = called_function_node_uuid
        self.context = context

    def serialize(self):
        csv_template = {
            'mandatory_node_dict': {
                # stub, this class represents only a relationship
            },
            'mandatory_relationship_dict': {
                'START_ID': self.callsite_instruction_node_uuid,
                'END_ID': self.called_function_node_uuid,
                'TYPE': 'FunctionCall',
                'StartNodeLabel': 'Instruction',
                'EndNodeLabel': 'Function',
            },

            'mandatory_context_dict': vars(self.context),

            'node_attributes': {
                # stub, this class represents only a relationship
            },
            'relationship_attributes': {

            },
        }

        return csv_template
