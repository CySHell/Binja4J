from binaryninja import *
import xxhash


################################################################################################################
#                                       MLIL Constant                                                          #
################################################################################################################

class Neo4jConstant:

    def __init__(self, constant, uuid, operand_index: int, context):
        self.UUID = uuid
        self.constant = constant
        self.operand_index = operand_index
        self.parent_expr_uuid = context.RootExpression
        self.HASH = self.constant_hash()
        self.context = context

    def constant_hash(self):
        constant_hash = xxhash.xxh64()
        constant_hash.update(str(self.constant))

        return constant_hash.hexdigest()

    def serialize(self):
        csv_template = {
            'mandatory_node_dict': {
                'HASH': self.HASH,
                'UUID': self.UUID,
                'LABEL': 'Constant',
                'ConstantValue': self.constant,
            },
            'mandatory_relationship_dict': {
                'START_ID': self.parent_expr_uuid,
                'END_ID': self.UUID,
                'TYPE': 'ConstantOperand',
                'StartNodeLabel': 'Expression',
                'EndNodeLabel': 'Constant',
            },

            'mandatory_context_dict': vars(self.context),

            'node_attributes': {
                'ConstType': type(self.constant)

            },
            'relationship_attributes': {
                'OperandIndex': self.operand_index,
            },
        }

        return csv_template
