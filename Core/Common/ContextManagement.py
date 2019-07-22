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

    def __init__(self, binaryview_uuid=None, function_uuid=None, basicblock_uuid=None, instruction_uuid=None,
                 expression_uuid=None, operand_index=None):
        self.RootBinaryView = binaryview_uuid or str()
        self.RootFunction = function_uuid or str()
        self.RootBasicBlock = basicblock_uuid or str()
        self.RootInstruction = instruction_uuid or str()
        self.RootExpression = expression_uuid or str()
        self.OperandIndex = str(operand_index) or str()
        self.SelfHASH = str()
        self.ParentHASH = str()
        self.ContextHash = str()
        self.SelfUUID = str()

    def __repr__(self):
        return ("RootBinaryView: " + str(self.RootBinaryView) + "\n" +
                "RootFunction: " + str(self.RootFunction) + "\n" +
                "RootBasicBlock: " + str(self.RootBasicBlock) + "\n" +
                "RootInstruction: " + str(self.RootInstruction) + "\n" +
                "RootExpression: " + str(self.RootExpression) + "\n" +
                "SelfHASH: " + str(self.SelfHASH) + "\n" +
                "ParentHASH: " + str(self.ParentHASH) + "\n" +
                "SelfUUID: " + str(self.SelfUUID) + "\n" +
                "OperandIndex" + str(self.OperandIndex) + "\n" +
                "*" * 30
                )

    def set_uuid(self, uuid):
        self.SelfUUID = uuid

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
        hash.update(self.SelfUUID)
        hash.update(self.ParentHASH)

        self.ContextHash = hash.hexdigest()

        return self.ContextHash

    def get_context(self):
        self.context_hash()
        return vars(self)
