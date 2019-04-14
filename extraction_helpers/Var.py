from binaryninja import *
import xxhash


################################################################################################################
#                                       MLIL Variable                                                          #
################################################################################################################

class Neo4jVar:

    def __init__(self, var, uuid, operand_index: int, parent_expr: int):
        self.UUID = uuid
        self.var = var
        self.source_variable_type = var.source_type
        self.type = str(var.type.tokens).strip('[').strip(']').replace(',', '').replace("'", '') if var.type else None
        self.operand_index = operand_index
        self.parent_expr = parent_expr
        self.HASH = self.var_hash()

    def var_hash(self):
        var_hash = xxhash.xxh32()
        var_hash.update(self.var.name)

        return var_hash.intdigest()

    def serialize(self):
        csv_template = {
            'mandatory_node_dict': {
                'HASH': self.HASH,
                'UUID': self.UUID,
                'LABEL': 'Variable',
            },
            'mandatory_relationship_dict': {
                'START_ID': self.parent_expr,
                'END_ID': self.UUID,
                'TYPE': 'VarOperand',
            },
            'node_attributes': {
                'SourceVarType': self.source_variable_type.name,
                'Type': self.type,
                'Name': self.var.name
            },
            'relationship_attributes': {
                'OperandIndex': self.operand_index,
            },
        }

        return csv_template
