from binaryninja import *
import xxhash


################################################################################################################
#                                       Symbol                                                                 #
################################################################################################################

class Neo4jSymbol:

    def __init__(self, symbol, uuid: str, parent_node_uuid: str, parent_node_type: str, binaryViewUUID: str):

        self.UUID = uuid
        self.binaryViewUUID = binaryViewUUID
        self.symbol = symbol
        self.HASH = self.symbol_hash()
        self.parent_node_uuid = parent_node_uuid
        self.parent_node_type = parent_node_type

    def symbol_hash(self):
        symbol_hash = xxhash.xxh64()
        symbol_hash.update(self.symbol.raw_name + str(self.symbol.type.value) + str(self.symbol.namespace))

        return symbol_hash.hexdigest()

    def serialize(self):
        csv_template = {
            'mandatory_node_dict': {
                'HASH': self.HASH,
                'UUID': self.UUID,
                'LABEL': 'Symbol',
            },
            'mandatory_relationship_dict': {
                'START_ID': self.parent_node_uuid,
                'END_ID': self.UUID,
                'TYPE': 'SymbolRef',
                'StartNodeLabel': self.parent_node_type,
                'EndNodeLabel': 'Symbol',
                'BinaryViewUUID': self.binaryViewUUID,
            },
            'node_attributes': {
                'SymbolName': self.symbol.raw_name,
                'SymbolTypeEnum': self.symbol.type.value,
                'SymbolType': self.symbol.type.name,
                'SymbolNameSpace': self.symbol.namespace,
            },
            'relationship_attributes': {
                'SymbolOrdinal': self.symbol.ordinal,
                'SymbolBinding': self.symbol.binding,
            },
        }

        return csv_template
