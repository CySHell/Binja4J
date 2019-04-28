from binaryninja import *
import xxhash

################################################################################################################
#                                       MLIL FUNCTION                                                          #
################################################################################################################

"""
UUID - _uuid of the node
HASH - xxhash of the full file assembly, NOT MLIL
"""


class Neo4jFunction:

    def __init__(self, mlil_func, uuid: int, relationship_label: str, bv_uuid: int):
        self.UUID = uuid
        self.func = mlil_func
        self.source_function = self.func.source_function
        self.bv = self.source_function.view
        self.HASH = self.func_hash()
        self.relationship_label = relationship_label
        self.bv_uuid = bv_uuid

    def func_hash(self):
        function_hash = xxhash.xxh32()
        br = BinaryReader(self.bv)

        for basic_block in self.source_function:
            br.seek(basic_block.start)
            bb_txt = br.read(basic_block.length)
            function_hash.update(bb_txt)

        return function_hash.intdigest()

    def serialize(self, caller_func: int = '0'):
        csv_template = {
            'mandatory_node_dict': {
                'UUID': self.UUID,
                'HASH': self.HASH,
                'LABEL': 'Function',
            },
            'mandatory_relationship_dict': {
                'START_ID': self.bv_uuid,
                'END_ID': self.UUID,
                'TYPE': self.relationship_label,
                'StartNodeLabel': 'BinaryView' if self.relationship_label is 'MemberFunc' else 'Function',
                'EndNodeLabel': 'Function',
            },
            'node_attributes': {

            },
            'relationship_attributes': {
                'Offset': self.source_function.start,
                'CallerFunc': caller_func,
            },
        }
        return csv_template
