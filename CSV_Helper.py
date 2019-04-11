import csv

path2 = 'C:\\Users\\user\\Downloads\\'
path = 'C:\\Users\\user\\.Neo4jDesktop\\neo4jDatabases\\database-e9d7bcc0-ef2d-413b-9bd1-a9611b47bc06\\installation-3.5.4\\\import\\'

class CSV_Serialize:

    def __init__(self):

        self.types = {
            'BinaryView': open(path + 'BinaryView-nodes.csv', 'w', buffering=1, encoding='utf-8', newline=''),
            'Function': open(path + 'Functions-nodes.csv', 'w', buffering=1, encoding='utf-8', newline=''),
            'BasicBlock': open(path + 'BasicBlocks-nodes.csv', 'w', buffering=1, encoding='utf-8', newline=''),
            'Instruction': open(path + 'Instructions-nodes.csv', 'w', buffering=1, encoding='utf-8', newline=''),
            'Expression': open(path + 'Expressions-nodes.csv', 'w', buffering=1, encoding='utf-8', newline=''),
            'Variable': open(path + 'Vars-nodes.csv', 'w', buffering=1, encoding='utf-8', newline=''),
            'MemberFunc': open(path + 'MemberFunc-relationships.csv', 'w', buffering=1, encoding='utf-8', newline=''),
            'Calls': open(path + 'Calls-relationships.csv', 'w', buffering=1, encoding='utf-8', newline=''),
            'MemberBB': open(path + 'MemberBB-relationships.csv', 'w', buffering=1, encoding='utf-8', newline=''),
            'Branch': open(path + 'Branch-relationships.csv', 'w', buffering=1, encoding='utf-8', newline=''),
            'InstructionChain': open(path + 'InstructionChain-relationships.csv', 'w', buffering=1, encoding='utf-8', newline=''),
            'NextInstruction': open(path + 'NextInstruction-relationships.csv', 'w', buffering=1, encoding='utf-8', newline=''),
            'BreakDown': open(path + 'BreakDown-relationships.csv', 'w', buffering=1, encoding='utf-8', newline=''),
            'Operand': open(path + 'Operand-relationships.csv', 'w', buffering=1, encoding='utf-8', newline=''),
            'MemberBV': open(path + 'MemberBV-relationships.csv', 'w', buffering=1, encoding='utf-8', newline=''),
        }

    def serialize_object(self, csv_template: dict):
        node_fieldnames = list(csv_template['mandatory_node_dict'])
        node_fieldnames.extend(list(csv_template['node_attributes']))
        relationship_fieldnames = list(csv_template['mandatory_relationship_dict'])
        relationship_fieldnames.extend(list(csv_template['relationship_attributes']))
        try:
            node_writer = csv.DictWriter(self.types[csv_template['mandatory_node_dict']['LABEL']], fieldnames=node_fieldnames)
            relationship_writer = csv.DictWriter(self.types[csv_template['mandatory_relationship_dict']['TYPE']],
                                                 fieldnames=relationship_fieldnames)

            if not self.types[csv_template['mandatory_node_dict']['LABEL']].tell():
                node_writer.writeheader()
            if not self.types[csv_template['mandatory_relationship_dict']['TYPE']].tell():
                relationship_writer.writeheader()

            node_writer.writerow(csv_template['mandatory_node_dict'])
            relationship_writer.writerow(csv_template['mandatory_relationship_dict'])

        except csv.Error:
            print("ERROR! writing to CSV failed on object: ", csv_template)
            return False
        return True

    def cleanup_csv(self):
        # TODO: implement this
        pass

    def close_file_handles(self):
        for file in self.types.values():
            print("closing: ", file)
            file.close()

    