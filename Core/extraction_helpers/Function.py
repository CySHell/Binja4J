from binaryninja import *
import xxhash

################################################################################################################
#                                       MLIL FUNCTION                                                          #
################################################################################################################


class Neo4jFunction:

    def __init__(self, mlil_func, uuid: str, context):
        self.UUID = uuid
        self.func = mlil_func
        self.source_function = self.func.source_function
        self.bv = self.source_function.view
        self.HASH = self.func_hash()
        self.context = context

    def func_hash(self):
        function_hash = xxhash.xxh64()
        br = BinaryReader(self.bv)

        for basic_block in self.source_function:
            br.seek(basic_block.start)
            bb_txt = br.read(basic_block.length)
            function_hash.update(bb_txt)

        return function_hash.hexdigest()

    def serialize(self):
        csv_template = {
            'mandatory_node_dict': {
                'UUID': self.UUID,
                'HASH': self.HASH,
                'LABEL': 'Function',
            },
            'mandatory_relationship_dict': {
                'START_ID': self.context.RootBinaryView,
                'END_ID': self.UUID,
                'TYPE': 'MemberFunc',
                'StartNodeLabel': 'BinaryView',
                'EndNodeLabel': 'Function',
                'Name': self.func.source_function.name,
                'Offset': self.source_function.start,
            },

            'mandatory_context_dict': vars(self.context),

            'node_attributes': {
                'ClobberedRegisters': self.func.source_function.clobbered_regs,
                'CallingConvention': self.func.source_function.calling_convention.name,
            },
            'relationship_attributes': {
            },
        }
        return csv_template
