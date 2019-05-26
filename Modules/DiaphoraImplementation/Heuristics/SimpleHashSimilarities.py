from Modules.DiaphoraImplementation import DiaFuncView


class SimpleFunctionSimilarities:
    # This class contains all simple Heuristics, in order to perform a quick and dirty narrow-down of possible matches

    def __init__(self, DFV: DiaFuncView):
        self.DFV = DFV
        self.SimilarityScore = {

        }

    def SameFileHash(self):
        # Check if Hash of both BinaryViews is identical

    def SameHash(self):
        # Check if Hash of both functions is identical

    def SameRVA(self):
        # Check if Relative Virtual Address is the same on both functions

    def SameImports(self):
        # Check if both functions have the same imports

    def SameSymbols(self):
