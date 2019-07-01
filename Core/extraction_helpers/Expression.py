from binaryninja import *
import xxhash


################################################################################################################
#                                       MLIL Expression                                                        #
################################################################################################################

class Neo4jExpression:

    def __init__(self, expression, uuid, context, parent_node_type: str,
                 operand_index: int):
        self.UUID = uuid
        self.operands = str(expression.operands)
        self.parent_expression = context.RootExpression if context.RootExpression else context.RootInstruction
        self.op_name = expression.operation.name
        self.op_type = str(expression.ILOperations[expression.operation])
        self.operand_index = operand_index
        self.parent_node_type = parent_node_type
        self.operation_enum = expression.operation.value
        self.HASH = self.expression_hash()
        self.context = context

    def expression_hash(self):
        expr_hash = xxhash.xxh64()
        expr_hash.update(self.operands + self.op_name)

        return expr_hash.hexdigest()

    def serialize(self):
        csv_template = {
            'mandatory_node_dict': {
                'UUID': self.UUID,
                'HASH': self.HASH,
                'LABEL': 'Expression',
            },
            'mandatory_relationship_dict': {
                'START_ID': self.parent_expression,
                'END_ID': self.UUID,
                'TYPE': 'Operand',
                'StartNodeLabel': self.parent_node_type,
                'EndNodeLabel': 'Expression',
            },

            'mandatory_context_dict': vars(self.context),

            'node_attributes': {
                'Operands': self.operands,
                'OperationName': self.op_name,
                'OperationEnum': self.operation_enum,
                'OperationType': self.op_type,
            },
            'relationship_attributes': {
                'OperandIndex': self.operand_index,
            },
        }

        return csv_template
