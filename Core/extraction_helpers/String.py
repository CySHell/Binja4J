from binaryninja import *
import xxhash


################################################################################################################
#                                       String                                                                 #
################################################################################################################

class Neo4jString:

    def __init__(self, raw_string: str, context, parent_node_type='Constant'):

        self.raw_string = self.sanitize_string(raw_string)
        self.context = context
        self.context.set_hash(self.string_hash())
        self.parent_node_type = parent_node_type

    def string_hash(self):
        string_hash = xxhash.xxh64()
        string_hash.update(str(self.raw_string).strip())

        return string_hash.hexdigest()

    def sanitize_string(self, raw_string):
        # Switch all quotation marks (' and ") with their ascii equivalent (%#%).
        # This is mainly done because neo4j can't parse complicated strings with many quotation marks.
        return raw_string.replace('"', '%34%').replace("'", "%39%")

    def serialize(self):
        csv_template = {
            'mandatory_node_dict': {
                'HASH': self.context.SelfHASH,
                'LABEL': 'String',
                'RawString': str(self.raw_string).strip(),
            },
            'mandatory_relationship_dict': {
                'START_ID': self.context.ParentHASH,
                'END_ID': self.context.SelfHASH,
                'TYPE': 'StringRef',
                'StartNodeLabel': self.parent_node_type,
                'EndNodeLabel': 'String',
            },

            'mandatory_context_dict': self.context.get_context(),

            'node_attributes': {
            },
            'relationship_attributes': {

            },
        }

        return csv_template
