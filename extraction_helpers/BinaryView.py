from binaryninja import *
import xxhash

################################################################################################################
#                                       BINARY VIEW                                                            #
################################################################################################################

"""
UUID - _uuid of the node
FILENAME - filename from which the function originated from
HASH - xxhash of the full file assembly, NOT MLIL
"""


class Neo4jBinaryView:
    """
    Extract all relevant info from a Binary View
    """

    def __init__(self, bv, uuid):
        """
        :param bv: (BinaryNinja bv object)
        :param uuid: (data_structures.UUID)
        """
        self.UUID = uuid
        self.FILENAME = bv.file.filename
        self.bv = bv
        self.HASH = self.bv_hash()

    def bv_hash(self):
        # create file object
        br = BinaryReader(self.bv)

        # calculate file hash
        # TODO: use external hash generators
        file_hash = xxhash.xxh32()
        # for some reason a BinaryReader won't read more then 1000 or so bytes
        temp_hash = br.read(1000)
        while temp_hash:
            file_hash.update(temp_hash)
            temp_hash = br.read(1000)

        return file_hash.intdigest()

    def serialize(self):
        csv_template = {
            'mandatory_node_dict': {
                'UUID': self.UUID,
                'HASH': self.HASH,
                'LABEL': 'BinaryView',
                },
            'mandatory_relationship_dict': {
                'START_ID': 0,
                'END_ID': self.UUID,
                'TYPE': 'MemberBV',
                'NodeLabel': 'BinaryView',
                'StartNodeLabel': 'MemberBV',
                'EndNodeLabel': 'MemberBV',
            },
            'node_attributes': {
                'FILENAME': self.FILENAME,
                'Architecture': self.bv.arch.name,
            },
            'relationship_attributes': {

            },
        }

        return csv_template
