from binaryninja import *
import xxhash


################################################################################################################
#                                       MLIL Expression                                                        #
################################################################################################################

class Neo4jExpression:

    def __init__(self, expression, context, parent_node_type: str,
                 operand_index: int):

        self.operands = str(expression.operands)
        self.op_name = expression.operation.name
        self.op_type = str(expression.ILOperations[expression.operation])
        self.operand_index = operand_index
        self.parent_node_type = parent_node_type
        self.operation_enum = expression.operation.value
        self.context = context
        self.context.set_hash(self.expression_hash())


    def expression_hash(self):
        expr_hash = xxhash.xxh64()
        expr_hash.update(self.operands + self.op_name)

        return expr_hash.hexdigest()

    def serialize(self):
        csv_template = {
            'mandatory_node_dict': {
                'HASH': self.context.SelfHASH,
                'LABEL': 'Expression',
                'Operands': self.operands,
                'OperationName': self.op_name,
                'OperationEnum': self.operation_enum,
                'OperationType': self.op_type,
            },
            'mandatory_relationship_dict': {
                'START_ID': self.context.ParentHASH,
                'END_ID': self.context.SelfHASH,
                'TYPE': 'Operand',
                'StartNodeLabel': self.parent_node_type,
                'EndNodeLabel': 'Expression',
            },

            'mandatory_context_dict': self.context.get_context(),

            'node_attributes': {

            },
            'relationship_attributes': {
            },
        }

        return csv_template
