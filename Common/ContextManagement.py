

class Context:
    # This class holds the context (i.e the current bv, RootFunction, bb etc) that we are working
    # under.
    # All values are specified as the corresponding UUID to the key.
    # This is added to each relationship in the graph so that traversal of the correct paths is easier and clearer.
    # During the export process to the Neo4j DB, all values are erased except for the RootBinaryView - This is
    # because if exactly the same object (function, instruction,basic block etc) exists in a different binary view
    # within the DB, then the UUID of that object is probably going to be different then the one mentioned here, yet
    # the same node object is used to represent the object.
    # TODO: expand this class to add more context related information, such as memory version etc

    def __init__(self, binaryview, function=None, basicblock=None, instruction=None, expression=None):
        self.RootBinaryView = binaryview
        self.RootFunction = function
        self.RootBasicBlock = basicblock
        self.RootInstruction = instruction
        self.RootExpression = expression


