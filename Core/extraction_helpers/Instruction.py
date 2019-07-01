from binaryninja import *
import xxhash


################################################################################################################
#                                       MLIL Instruction                                                       #
################################################################################################################

class Neo4jInstruction:

    def __init__(self, instr, uuid: int, context):
        self.UUID = uuid
        self.instr = instr
        self.HASH = self.instr_hash()
        self.operands = str(instr.operands)
        self.context = context
        if self.instr.instr_index == 0:
            self.relationship_label = 'InstructionChain'
            self.parent_instruction_uuid = context.RootBasicBlock
        else:
            self.relationship_label = 'NextInstruction'
            self.parent_instruction_uuid = context.RootInstruction



    def instr_hash(self):
        instruction_hash = xxhash.xxh64()
        instruction_hash.update(str(self.instr.operands) + str(self.instr.operation))

        return instruction_hash.hexdigest()

    def serialize(self):
        csv_template = {
            'mandatory_node_dict': {
                'UUID': self.UUID,
                'HASH': self.HASH,
                'LABEL': 'Instruction',
            },
            'mandatory_relationship_dict': {
                'START_ID': self.parent_instruction_uuid,
                'END_ID': self.UUID,
                'TYPE': self.relationship_label,
                'StartNodeLabel': 'BasicBlock' if self.relationship_label is 'InstructionChain' else 'Instruction',
                'EndNodeLabel': 'Instruction',
            },

            'mandatory_context_dict': vars(self.context),

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
