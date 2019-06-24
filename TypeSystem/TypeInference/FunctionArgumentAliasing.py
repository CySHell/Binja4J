from binaryninja import *


class FuncArgAliases:

    def __init__(self, func):
        """
        :param func: BinaryNinja MLIL_FUNCTION object
        """
        self.func = func
        self.bv = self.func.source_function.view


    def alias_func_args(self):
        """
        This function is the entry point to this class, and is responsbile to alias MLIL variables according to
        their type and name as defined by the function type.
        """

        for reffering_address in [ref.address for ref in self.bv.get_code_refs(self.func.source_function.start)]:
