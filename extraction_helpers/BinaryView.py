from binaryninja import *
import xxhash

################################################################################################################
#                                       BINARY VIEW                                                            #
################################################################################################################


class Neo4jBinaryView:
    """
    Extract all relevant info from a Binary View itself
    """

    def __init__(self, bv, uuid: str):
        """
        :param bv: (BinaryNinja bv object)
        :param uuid: uuid to assign this bv object
        """
        self.UUID = uuid
        self.FILENAME = bv.file.filename
        self.bv = bv
        self.HASH = self.bv_hash()

    def bv_hash(self):
        """
        Iterate over all the BinaryView (flat iteration over the hex values themselves)
        :return:(INT) Hash  of the whole file
        """

        # create file object
        br = BinaryReader(self.bv)

        # calculate file hash
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
