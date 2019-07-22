from binaryninja import *
from ..Common import ContextManagement
import xxhash

################################################################################################################
#                                       BINARY VIEW                                                            #
################################################################################################################


class Neo4jBinaryView:
    """
    Extract all relevant info from a Binary View itself
    """

    def __init__(self, bv):

        self.FILENAME = bv.file.filename
        self.bv = bv
        self.context = ContextManagement.Context()
        self.context.set_hash(self.bv_hash())
        self.context.set_uuid("BV" + self.context.SelfHASH)
        self.context.set_parent_hash('0')

    def bv_hash(self):
        """
        Iterate over all the BinaryView (flat iteration over the hex values themselves)
        :return:(INT) Hash  of the whole file
        """

        # create file object
        br = BinaryReader(self.bv)

        # calculate file hash
        file_hash = xxhash.xxh64()
        # for some reason a BinaryReader won't read more then 1000 or so bytes
        temp_hash = br.read(1000)
        while temp_hash:
            file_hash.update(temp_hash)
            temp_hash = br.read(1000)

        return file_hash.hexdigest()

    def serialize(self):

        csv_template = {
            'mandatory_node_dict': {
                'HASH': self.context.SelfHASH,
                'LABEL': 'BinaryView',
                },
            'mandatory_relationship_dict': {
                'START_ID': 0,
                'END_ID': self.context.SelfHASH,
                'TYPE': 'MemberBV',
                'NodeLabel': 'BinaryView',
                'StartNodeLabel': 'MemberBV',
                'EndNodeLabel': 'MemberBV',
            },
            'mandatory_context_dict': self.context.get_context(),

            'node_attributes': {
                'FILENAME': self.FILENAME,
                'Architecture': self.bv.arch.name,
            },
            'relationship_attributes': {

            },
        }

        return csv_template
