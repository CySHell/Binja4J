import csv
from . import Configuration


class CSV_Serialize:

    def __init__(self):

        self.types = {
            'BinaryView': open(Configuration.path + 'BinaryView-nodes.csv', 'w', buffering=1, encoding='utf-8',
                               newline=''),
            'Function': open(Configuration.path + 'Functions-nodes.csv', 'w', buffering=1, encoding='utf-8',
                             newline=''),
            'BasicBlock': open(Configuration.path + 'BasicBlocks-nodes.csv', 'w', buffering=1, encoding='utf-8',
                               newline=''),
            'Instruction': open(Configuration.path + 'Instructions-nodes.csv', 'w', buffering=1, encoding='utf-8',
                                newline=''),
            'Expression': open(Configuration.path + 'Expressions-nodes.csv', 'w', buffering=1, encoding='utf-8',
                               newline=''),
            'Variable': open(Configuration.path + 'Vars-nodes.csv', 'w', buffering=1, encoding='utf-8', newline=''),
            'MemberFunc': open(Configuration.path + 'MemberFunc-relationships.csv', 'w', buffering=1, encoding='utf-8',
                               newline=''),
            'Calls': open(Configuration.path + 'Calls-relationships.csv', 'w', buffering=1, encoding='utf-8',
                          newline=''),
            'MemberBB': open(Configuration.path + 'MemberBB-relationships.csv', 'w', buffering=1, encoding='utf-8',
                             newline=''),
            'Branch': open(Configuration.path + 'Branch-relationships.csv', 'w', buffering=1, encoding='utf-8',
                           newline=''),
            'InstructionChain': open(Configuration.path + 'InstructionChain-relationships.csv', 'w', buffering=1,
                                     encoding='utf-8', newline=''),
            'NextInstruction': open(Configuration.path + 'NextInstruction-relationships.csv', 'w', buffering=1,
                                    encoding='utf-8', newline=''),
            'BreakDown': open(Configuration.path + 'BreakDown-relationships.csv', 'w', buffering=1, encoding='utf-8',
                              newline=''),
            'Operand': open(Configuration.path + 'Operand-relationships.csv', 'w', buffering=1, encoding='utf-8',
                            newline=''),
            'VarOperand': open(Configuration.path + 'VarOperand-relationships.csv', 'w', buffering=1, encoding='utf-8',
                               newline=''),
            'MemberBV': open(Configuration.path + 'MemberBV-relationships.csv', 'w', buffering=1, encoding='utf-8',
                             newline=''),
            'ConstantOperand': open(Configuration.path + 'ConstantOperand-relationships.csv', 'w', buffering=1,
                                    encoding='utf-8', newline=''),
            'Constant': open(Configuration.path + 'Constant-nodes.csv', 'w', buffering=1, encoding='utf-8', newline=''),
        }

    def serialize_object(self, csv_template: dict, write_node=True, write_relationship=True):
        try:
            if write_node:
                node_fieldnames = list(csv_template['mandatory_node_dict'])
                node_fieldnames.extend(list(csv_template['node_attributes']))
                node_writer = csv.DictWriter(self.types[csv_template['mandatory_node_dict']['LABEL']],
                                             fieldnames=node_fieldnames)
                if not self.types[csv_template['mandatory_node_dict']['LABEL']].tell():
                    node_writer.writeheader()
                node_row = csv_template['mandatory_node_dict']
                if csv_template['node_attributes']:
                    node_row.update(csv_template['node_attributes'])
                node_writer.writerow(node_row)

            if write_relationship:
                relationship_fieldnames = list(csv_template['mandatory_relationship_dict'])
                relationship_fieldnames.extend(list(csv_template['relationship_attributes']))
                relationship_writer = csv.DictWriter(self.types[csv_template['mandatory_relationship_dict']['TYPE']],
                                                     fieldnames=relationship_fieldnames)
                if not self.types[csv_template['mandatory_relationship_dict']['TYPE']].tell():
                    relationship_writer.writeheader()
                relationship_row = csv_template['mandatory_relationship_dict']
                if csv_template['relationship_attributes']:
                    relationship_row.update(csv_template['relationship_attributes'])
                relationship_writer.writerow(relationship_row)

        except csv.Error:
            print("ERROR! writing to CSV failed on object: ", csv_template)
            return False
        return True

    def close_file_handles(self):
        for file in self.types.values():
            file.close()
