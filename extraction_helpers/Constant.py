from binaryninja import *
import xxhash


################################################################################################################
#                                       MLIL Constant                                                          #
################################################################################################################

class Neo4jConstant:

    def __init__(self, constant, uuid, operand_index: int, parent_expr: int):
        self.UUID = uuid
        self.constant = constant
        self.operand_index = operand_index
        self.parent_expr = parent_expr
        self.HASH = self.constant_hash()

    def constant_hash(self):
        constant_hash = xxhash.xxh32()
        constant_hash.update(str(self.constant))

        return constant_hash.intdigest()

    def serialize(self):
        csv_template = {
            'mandatory_node_dict': {
                'HASH': self.HASH,
                'UUID': self.UUID,
                'LABEL': 'Constant',
            },
            'mandatory_relationship_dict': {
                'START_ID': self.parent_expr,
                'END_ID': self.UUID,
                'TYPE': 'ConstantOperand',
            },
            'node_attributes': {
                'ConstType': type(self.constant)
            },
            'relationship_attributes': {
                'OperandIndex': self.operand_index,
            },
        }

        return csv_template
