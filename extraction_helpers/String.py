from binaryninja import *
import xxhash


################################################################################################################
#                                       String                                                                 #
################################################################################################################

class Neo4jString:

    def __init__(self, raw_string, uuid: str, parent_node_uuid: str, parent_node_type: str, binaryViewUUID: str):

        self.UUID = uuid
        self.binaryViewUUID = binaryViewUUID
        self.raw_string = raw_string
        self.HASH = self.string_hash()
        self.parent_node_uuid = parent_node_uuid
        self.parent_node_type = parent_node_type

    def string_hash(self):
        string_hash = xxhash.xxh64()
        string_hash.update(self.raw_string)

        return string_hash.hexdigest()

    def serialize(self):
        csv_template = {
            'mandatory_node_dict': {
                'HASH': self.HASH,
                'UUID': self.UUID,
                'LABEL': 'String',
            },
            'mandatory_relationship_dict': {
                'START_ID': self.parent_node_uuid,
                'END_ID': self.UUID,
                'TYPE': 'StringRef',
                'StartNodeLabel': self.parent_node_type,
                'EndNodeLabel': 'String',
                'BinaryViewUUID': self.binaryViewUUID,
            },
            'node_attributes': {
                'RawString': str(self.raw_string).strip(),
            },
            'relationship_attributes': {

            },
        }

        return csv_template
