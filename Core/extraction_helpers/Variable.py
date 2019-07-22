from binaryninja import *
import xxhash


################################################################################################################
#                                       MLIL Variable                                                          #
################################################################################################################

class Neo4jVar:

    def __init__(self, var, operand_index: int, context):
        self.var = var
        self.source_variable_type = var.source_type
        self.type = str(var.type.tokens).strip('[').strip(']').replace(',', '').replace("'", '') if var.type else None
        self.operand_index = operand_index
        self.context = context
        self.context.set_hash(self.var_hash())

    def var_hash(self):
        var_hash = xxhash.xxh64()
        var_hash.update(self.var.name + str(self.source_variable_type))

        return var_hash.hexdigest()

    def serialize(self):
        csv_template = {
            'mandatory_node_dict': {
                'HASH': self.context.SelfHASH,
                'LABEL': 'Variable',
            },
            'mandatory_relationship_dict': {
                'START_ID': self.context.ParentHASH,
                'END_ID': self.context.SelfHASH,
                'TYPE': 'VarOperand',
                'StartNodeLabel': 'Expression',
                'EndNodeLabel': 'Variable',
                'VariableDefinedAtIndex': ', '.join(map(str, self.var.function.mlil.get_var_definitions(self.var))),
                'VariableUsedAtIndex': ', '.join(map(str, self.var.function.mlil.get_var_uses(self.var))),
            },

            'mandatory_context_dict': self.context.get_context(),

            'node_attributes': {
                'SourceVarType': self.source_variable_type.name,
                'SourceVarTypeEnum': self.source_variable_type.value,
                'Type': self.type,
                'Name': self.var.name
            },
            'relationship_attributes': {
            },
        }
        return csv_template
