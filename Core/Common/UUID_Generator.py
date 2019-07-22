class UUID:
    """
    UUID object, used to synchronize the UUID of any new object created in the graph.
    The UUID of an object is the 32 bit HASH of the binary view assembly instructions, concactenated with
    the objects' offset within the bv.
    """

    def __init__(self, bv_hash):
        """
        :param bv_hash: (INT) A hash of the binary view assembly
        """

        self.bv_hash = str(bv_hash)

    def get_uuid(self, offset):
        """
        returns a single uuid for a consumer of the class to use.
        :return: uuid: (string)
        """
        return self.bv_hash + str(offset) + '-'
