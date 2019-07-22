from binaryninja import *
import xxhash

################################################################################################################
#                                       MLIL FUNCTION                                                          #
################################################################################################################


class Neo4jFunction:

    def __init__(self, mlil_func, context):
        self.func = mlil_func
        self.source_function = self.func.source_function
        self.bv = self.source_function.view
        self.context = context
        self.context.set_hash(self.func_hash())

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
                'HASH': self.context.SelfHASH,
                'LABEL': 'Function',
            },
            'mandatory_relationship_dict': {
                'START_ID': self.context.ParentHASH,
                'END_ID': self.context.SelfHASH,
                'TYPE': 'MemberFunc',
                'StartNodeLabel': 'BinaryView',
                'EndNodeLabel': 'Function',
                'Name': str(self.func.source_function.name),
                'Offset': self.source_function.start,
            },

            'mandatory_context_dict': self.context.get_context(),

            'node_attributes': {
                'ClobberedRegisters': self.func.source_function.clobbered_regs,
                'CallingConvention': self.func.source_function.calling_convention.name,
            },
            'relationship_attributes': {

            },
        }
        return csv_template
