from binaryninja import *
import xxhash

################################################################################################################
#                                       MLIL BASIC BLOCK                                                       #
################################################################################################################

"""
HASH - xxhash of the basic block, created by digesting all tokens from all instructions within the basic block
"""


class Neo4jBasicBlock:

    def __init__(self, bb, uuid: int, parent_func_uuid: int, parent_bb_uuid: int, branch_condition_enum: int):
        """
        Init the BasicBlock node
        """
        self.UUID = uuid
        self.bb = bb
        self.HASH = self.bb_hash()
        self.relationship_label = 'MemberBB' if not bb.incoming_edges else 'Branch'
        self.parent_func_uuid = parent_func_uuid
        self.parent_bb = parent_bb_uuid
        self.branch_condition_enum = branch_condition_enum

    def bb_hash(self):
        mlil_bb_hash = xxhash.xxh32()

        for disasm_text in self.bb.disassembly_text:
            if 'sub_' not in str(disasm_text):
                mlil_bb_hash.update(str(disasm_text))

        return mlil_bb_hash.intdigest()

    def serialize(self):
        """
        Serialize the BasicBlock object into a CSV file
        :param parent_bb: UUID of the parent BB. Null if this is the first BB in the function
        :return:
        """

        csv_template = {
            'mandatory_node_dict': {
                'UUID': self.UUID,
                'HASH': self.HASH,
                'LABEL': 'BasicBlock',
            },
            'mandatory_relationship_dict': {
                'START_ID': self.parent_bb,
                'BranchCondition': self.branch_condition_enum,
                'END_ID': self.UUID,
                'TYPE': self.relationship_label,
            },
            'node_attributes': {
                'node_test': 'node1',
            },
            'relationship_attributes': {
                'bb_offset': self.bb.start,
                'ParentFunction': self.parent_func_uuid,
            },
        }

        return csv_template


