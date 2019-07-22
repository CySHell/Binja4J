from binaryninja import *
import xxhash


################################################################################################################
#                                       Symbol                                                                 #
################################################################################################################

class Neo4jSymbol:

    def __init__(self, raw_symbol,  context, parent_node_type='Constant'):

        self.symbol = raw_symbol
        self.context = context
        self.context.set_hash(self.symbol_hash())
        self.parent_node_type = parent_node_type

    def symbol_hash(self):
        symbol_hash = xxhash.xxh64()
        symbol_hash.update(self.symbol.raw_name + str(self.symbol.type.value) + str(self.symbol.namespace))

        return symbol_hash.hexdigest()

    def serialize(self):
        csv_template = {
            'mandatory_node_dict': {
                'HASH': self.context.SelfHASH,
                'LABEL': 'Symbol',
                'SymbolName': self.symbol.raw_name,
                'SymbolTypeEnum': self.symbol.type.value,
                'SymbolType': self.symbol.type.name,
                'SymbolNameSpace': self.symbol.namespace,
            },
            'mandatory_relationship_dict': {
                'START_ID': self.context.ParentHASH,
                'END_ID': self.context.SelfHASH,
                'TYPE': 'SymbolRef',
                'StartNodeLabel': self.parent_node_type,
                'EndNodeLabel': 'Symbol',
            },

            'mandatory_context_dict': self.context.get_context(),

            'node_attributes': {
            },
            'relationship_attributes': {
                'SymbolOrdinal': self.symbol.ordinal,
                'SymbolBinding': self.symbol.binding,
            },
        }
        return csv_template
