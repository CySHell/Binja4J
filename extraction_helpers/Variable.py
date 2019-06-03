from binaryninja import *
import xxhash


################################################################################################################
#                                       MLIL Variable                                                          #
################################################################################################################

class Neo4jVar:

    def __init__(self, var, uuid, operand_index: int, parent_expr_uuid: str, context):
        self.UUID = uuid
        self.var = var
        self.source_variable_type = var.source_type
        self.type = str(var.type.tokens).strip('[').strip(']').replace(',', '').replace("'", '') if var.type else None
        self.operand_index = operand_index
        self.parent_expr = parent_expr_uuid
        self.HASH = self.var_hash()
        self.context = context

    def var_hash(self):
        var_hash = xxhash.xxh64()
        var_hash.update(self.var.name + str(self.source_variable_type))

        return var_hash.hexdigest()

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
                'StartNodeLabel': 'Expression',
                'EndNodeLabel': 'Variable',
            },

            'mandatory_context_dict': vars(self.context),

            'node_attributes': {
                'SourceVarType': self.source_variable_type.name,
                'SourceVarTypeEnum': self.source_variable_type.value,
                'Type': self.type,
                'Name': self.var.name
            },
            'relationship_attributes': {
                'OperandIndex': self.operand_index,
                'VariableDefinedAtIndex': ', '.join(map(str, self.var.function.mlil.get_var_definitions(self.var))),
                'VariableUsedAtIndex': ', '.join(map(str, self.var.function.mlil.get_var_uses(self.var))),
            },
        }
        return csv_template
