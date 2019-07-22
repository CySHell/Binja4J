# 1. INPUT:
#   - ContextManagement.context object:
#       * function UUID
#       * BinaryView UUID
#       * Variable UUID
#       * Instruction UUID ( Where Variable was defined )
#       * No need for BasicBlock UUID
# 2.



class BackwardsSlicePathTree:
    # This class represents a single backwards slice path on a single variable.
    # The class is represented as a tree, with the variable as the root and subsequest expressions as its children

