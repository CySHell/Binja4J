from binaryninja import *
import xxhash


################################################################################################################
#                                       MLIL BASIC BLOCK                                                       #
################################################################################################################

class Neo4jBasicBlock:

    def __init__(self, bb, branch_condition_enum: int, context, back_edge=False):
        """
        Init the BasicBlock node
        """
        self.bb = bb
        self.context = context
        if bb.index == 0:
            # The basic block is the first block in the function, so its parent is a function
            self.relationship_label = 'MemberBB'
        else:
            self.relationship_label = 'Branch'
        self.branch_condition_enum = branch_condition_enum
        self.BackEdge = back_edge
        self.context.set_hash(self.bb_hash())

    def bb_hash(self):
        node_hash = xxhash.xxh64()

        for disasm_text in self.bb.disassembly_text:
            if not str(disasm_text).startswith('sub_'):
                node_hash.update(str(disasm_text))

        return node_hash.hexdigest()

    def serialize(self):
        """
        Serialize the BasicBlock object into a dictionary
        """
        csv_template = {
            'mandatory_node_dict': {
                'HASH': self.context.SelfHASH,
                'LABEL': 'BasicBlock',
            },
            'mandatory_relationship_dict': {
                'START_ID': self.context.ParentHASH,
                'BranchCondition': self.branch_condition_enum,
                'END_ID': self.context.SelfHASH,
                'TYPE': self.relationship_label,
                'StartNodeLabel': 'Function' if self.relationship_label is 'MemberBB' else 'BasicBlock',
                'EndNodeLabel': 'BasicBlock',
                'BackEdge': self.BackEdge,
            },

            'mandatory_context_dict': self.context.get_context(),

            'node_attributes': {
            },
            'relationship_attributes': {
            },
        }

        return csv_template
