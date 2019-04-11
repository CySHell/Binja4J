from binaryninja import *
import xxhash


################################################################################################################
#                                       MLIL Expression                                                        #
################################################################################################################

class Neo4jExpression:

    def __init__(self, operand_list: list, uuid, parent_instruction: int, op_description_name: str,
                 op_description_type: str, operand_index: int):
        self.UUID = uuid
        self.operands = str(operand_list)
        self.HASH = self.expression_hash()
        self.parent_instruction = parent_instruction
        self.op_name = op_description_name
        self.op_type = op_description_type
        self.operand_index = operand_index

    def expression_hash(self):
        expr_hash = xxhash.xxh32()
        expr_hash.update(str(self.operands))

        return expr_hash.intdigest()

    def serialize(self):

        csv_template = {
            'mandatory_node_dict': {
                'UUID': self.UUID,
                'HASH': self.HASH,
                'LABEL': 'Expression',
            },
            'mandatory_relationship_dict': {
                'START_ID': self.parent_instruction,
                'END_ID': self.UUID,
                'TYPE': 'Operand',
            },
            'node_attributes': {
                'Operands': self.operands,
                'OperationName': self.op_name,
                'OperationType': self.op_type,
            },
            'relationship_attributes': {
                'OperandIndex': self.operand_index,
            },
        }

        return csv_template
