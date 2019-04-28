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
        self.relationship_label = 'MemberBB' if not bb.incoming_edges else 'Branch'
        self.parent_func_uuid = parent_func_uuid
        self.parent_bb = parent_bb_uuid
        self.branch_condition_enum = branch_condition_enum
        self.NODE_HASH, self.RELATIONSHIP_HASH = self.bb_hash()

    def bb_hash(self):
        node_hash = xxhash.xxh32()
        relationship_hash = xxhash.xxh32()

        for disasm_text in self.bb.disassembly_text:
            if 'sub_' not in str(disasm_text):
                node_hash.update(str(disasm_text))

        relationship_hash.update(str(self.parent_func_uuid) + str(self.parent_bb) + str(self.UUID))

        return node_hash.intdigest(), relationship_hash.intdigest()

    def serialize(self):
        """
        Serialize the BasicBlock object into a CSV file
        :param parent_bb: UUID of the parent BB. Null if this is the first BB in the function
        :return:
        """

        csv_template = {
            'mandatory_node_dict': {
                'UUID': self.UUID,
                'HASH': self.NODE_HASH,
                'LABEL': 'BasicBlock',
            },
            'mandatory_relationship_dict': {
                'START_ID': self.parent_bb,
                'BranchCondition': self.branch_condition_enum,
                'END_ID': self.UUID,
                'TYPE': self.relationship_label,
                'REL_HASH': self.RELATIONSHIP_HASH,
                'StartNodeLabel': 'Function' if self.relationship_label is 'MemberBB' else 'BasicBlock',
                'EndNodeLabel': 'BasicBlock'
            },
            'node_attributes': {
            },
            'relationship_attributes': {
                'bb_offset': self.bb.start,
                'ParentFunctionUUID': self.parent_func_uuid,
                'bbRawOffset': self.bb.source_block.start
            },
        }

        return csv_template


