from binaryninja import *
import xxhash


################################################################################################################
#                                       MLIL Instruction                                                       #
################################################################################################################

class Neo4jInstruction:

    def __init__(self, instr, uuid: int, relationship_label: str, parent_bb:int, parent_instruction: int):
        self.UUID = uuid
        self.instr = instr
        self.HASH = self.instr_hash()
        self.operands = str(instr.operands)
        self.relationship_label = relationship_label
        self.parent_bb = parent_bb
        self.parent_instruction = parent_instruction

    def instr_hash(self):
        instruction_hash = xxhash.xxh32()
        instruction_hash.update(str(self.instr.tokens).strip('[').strip(']').replace("'", '').replace(",", ''))

        return instruction_hash.intdigest()

    def serialize(self):
        csv_template = {
            'mandatory_node_dict': {
                'UUID': self.UUID,
                'HASH': self.HASH,
                'Operands': self.operands,
                'LABEL': 'Instruction',
            },
            'mandatory_relationship_dict': {
                'START_ID': self.parent_instruction,
                'InstructionIndex': self.instr.instr_index,
                'ParentBB': self.parent_bb,
                'END_ID': self.UUID,
                'TYPE': self.relationship_label,
            },
            'node_attributes': {

            },
            'relationship_attributes': {

            },
        }
        return csv_template
