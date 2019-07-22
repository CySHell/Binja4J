from binaryninja import *
import xxhash


################################################################################################################
#                                       MLIL Constant                                                          #
################################################################################################################

class Neo4jConstant:

    def __init__(self, constant, operand_index: int, context):
        self.constant = constant
        self.operand_index = operand_index
        self.context = context
        self.context.set_hash(self.constant_hash())

    def constant_hash(self):
        constant_hash = xxhash.xxh64()
        constant_hash.update(str(self.constant))

        return constant_hash.hexdigest()

    def serialize(self):

        csv_template = {
            'mandatory_node_dict': {
                'HASH': self.context.SelfHASH,
                'LABEL': 'Constant',
                'ConstantValue': self.constant,
            },
            'mandatory_relationship_dict': {
                'START_ID': self.context.ParentHASH,
                'END_ID': self.context.SelfHASH,
                'TYPE': 'ConstantOperand',
                'StartNodeLabel': 'Expression',
                'EndNodeLabel': 'Constant',
            },

            'mandatory_context_dict': self.context.get_context(),

            'node_attributes': {
                'ConstType': type(self.constant)

            },
            'relationship_attributes': {
            },
        }

        return csv_template
