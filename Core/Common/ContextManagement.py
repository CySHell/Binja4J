import xxhash


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

    def __init__(self, binaryview_hash=None, function_hash=None, basicblock_hash=None, instruction_hash=None,
                 expression_hash=None, operand_index=None):
        self.RootBinaryView = binaryview_hash or str()
        self.RootFunction = function_hash or str()
        self.RootBasicBlock = basicblock_hash or str()
        self.RootInstruction = instruction_hash or str()
        self.RootExpression = expression_hash or str()
        self.OperandIndex = str(operand_index) or str()
        self.SelfHASH = str()
        self.ParentHASH = str()
        self.ContextHash = str()

    def __repr__(self):
        return ("RootBinaryView: " + str(self.RootBinaryView) + "\n" +
                "RootFunction: " + str(self.RootFunction) + "\n" +
                "RootBasicBlock: " + str(self.RootBasicBlock) + "\n" +
                "RootInstruction: " + str(self.RootInstruction) + "\n" +
                "RootExpression: " + str(self.RootExpression) + "\n" +
                "SelfHASH: " + str(self.SelfHASH) + "\n" +
                "ParentHASH: " + str(self.ParentHASH) + "\n" +
                "OperandIndex" + str(self.OperandIndex) + "\n" +
                "*" * 30
                )

    def set_hash(self, hash):
        self.SelfHASH = hash

    def set_parent_hash(self, p_hash):
        self.ParentHASH = p_hash

    def context_hash(self):
        hash = xxhash.xxh64()

        hash.update(self.RootBinaryView)
        hash.update(self.RootFunction)
        hash.update(self.RootBasicBlock)
        hash.update(self.RootInstruction)
        hash.update(self.RootExpression)
        hash.update(self.ParentHASH)
        hash.update(self.SelfHASH)

        self.ContextHash = hash.hexdigest()

        return self.ContextHash

    def get_context(self):
        self.context_hash()
        return vars(self)
