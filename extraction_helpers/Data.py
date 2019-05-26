from binaryninja import *
import xxhash


################################################################################################################
#                                       DATA                                                                   #
################################################################################################################

class Neo4jData:

    def __init__(self, raw_data, uuid: str, data_type: str, parent_node_uuid: str,
                 parent_node_type: str, binaryViewUUID: str):

        self.UUID = uuid
        self.binaryViewUUID = binaryViewUUID
        self.raw_data = raw_data
        self.data_type = data_type
        self.HASH = self.data_hash()
        self.parent_node_uuid = parent_node_uuid
        self.parent_node_type = parent_node_type

    def data_hash(self):
        data_hash = xxhash.xxh64()
        data_hash.update(str(self.raw_data) + self.data_type)

        return data_hash.hexdigest()

    def serialize(self):
        csv_template = {
            'mandatory_node_dict': {
                'HASH': self.HASH,
                'UUID': self.UUID,
                'LABEL': self.data_type,
            },
            'mandatory_relationship_dict': {
                'START_ID': self.parent_node_uuid,
                'END_ID': self.UUID,
                'TYPE': 'Data',
                'StartNodeLabel': self.parent_node_type,
                'EndNodeLabel': self.data_type,
                'BinaryViewUUID': self.binaryViewUUID,
            },
            'node_attributes': {
                'RawData': str(self.raw_data).strip(),
            },
            'relationship_attributes': {

            },
        }

        return csv_template
