from binaryninja import *
import xxhash


################################################################################################################
#                                       MLIL Instruction                                                       #
################################################################################################################

class Neo4jInstruction:

    def __init__(self, instr: mediumlevelil.MediumLevelILInstruction, context, parent_type: str):
        self.instr = instr
        self.parent_type = parent_type
        self.operands = str(instr.operands)
        self.context = context

        if self.parent_type == 'BasicBlock':
            self.relationship_label = 'InstructionChain'
        else:
            self.relationship_label = 'NextInstruction'

        self.context.set_hash(self.instr_hash())

    def instr_hash(self):
        instruction_hash = xxhash.xxh64()
        instruction_hash.update(str(self.instr.operands) + str(self.instr.operation))

        return instruction_hash.hexdigest()

    def serialize(self):
        csv_template = {
            'mandatory_node_dict': {
                'HASH': self.context.SelfHASH,
                'LABEL': 'Instruction',
            },
            'mandatory_relationship_dict': {
                'START_ID': self.context.ParentHASH,
                'END_ID': self.context.SelfHASH,
                'TYPE': self.relationship_label,
                'StartNodeLabel': self.parent_type,
                'EndNodeLabel': 'Instruction',
                'AssemblyOffset': self.instr.address,
            },

            'mandatory_context_dict': self.context.get_context(),

            'node_attributes': {
            },
            'relationship_attributes': {
                'InstructionIndex': self.instr.instr_index,
                'PossibleValues': self.instr.possible_values.type.value,
                'VarsRead': [var.name for var in self.instr.vars_read],
                'VarsWritten': [var.name for var in self.instr.vars_written],
            },
        }
        return csv_template
