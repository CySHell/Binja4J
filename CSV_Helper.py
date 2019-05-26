import csv
from . import Configuration


class CSV_Serialize:

    def __init__(self):

        self.BinaryView = open(Configuration.path + 'BinaryView-nodes.csv', 'w+', buffering=1, encoding='utf-8',
                               newline='')
        self.Function = open(Configuration.path + 'Functions-nodes.csv', 'w+', buffering=1, encoding='utf-8',
                             newline='')
        self.BasicBlock = open(Configuration.path + 'BasicBlocks-nodes.csv', 'w+', buffering=1, encoding='utf-8',
                               newline='')
        self.Instruction = open(Configuration.path + 'Instructions-nodes.csv', 'w+', buffering=1, encoding='utf-8',
                                newline='')
        self.Expression = open(Configuration.path + 'Expressions-nodes.csv', 'w+', buffering=1, encoding='utf-8',
                               newline='')
        self.Variable = open(Configuration.path + 'Vars-nodes.csv', 'w+', buffering=1, encoding='utf-8', newline='')
        self.MemberFunc = open(Configuration.path + 'MemberFunc-relationships.csv', 'w+', buffering=1, encoding='utf-8',
                               newline='')
        self.Calls = open(Configuration.path + 'Calls-relationships.csv', 'w+', buffering=1, encoding='utf-8',
                          newline='')
        self.MemberBB = open(Configuration.path + 'MemberBB-relationships.csv', 'w+', buffering=1, encoding='utf-8',
                             newline='')
        self.Branch = open(Configuration.path + 'Branch-relationships.csv', 'w+', buffering=1, encoding='utf-8',
                           newline='')
        self.InstructionChain = open(Configuration.path + 'InstructionChain-relationships.csv', 'w+', buffering=1,
                                     encoding='utf-8', newline='')
        self.NextInstruction = open(Configuration.path + 'NextInstruction-relationships.csv', 'w+', buffering=1,
                                    encoding='utf-8', newline='')
        self.BreakDown = open(Configuration.path + 'BreakDown-relationships.csv', 'w+', buffering=1, encoding='utf-8',
                              newline='')
        self.Operand = open(Configuration.path + 'Operand-relationships.csv', 'w+', buffering=1, encoding='utf-8',
                            newline='')
        self.VarOperand = open(Configuration.path + 'VarOperand-relationships.csv', 'w+', buffering=1, encoding='utf-8',
                               newline='')
        self.MemberBV = open(Configuration.path + 'MemberBV-relationships.csv', 'w+', buffering=1, encoding='utf-8',
                             newline='')
        self.ConstantOperand = open(Configuration.path + 'ConstantOperand-relationships.csv', 'w+', buffering=1,
                                    encoding='utf-8', newline='')
        self.Constant = open(Configuration.path + 'Constant-nodes.csv', 'w+', buffering=1, encoding='utf-8', newline='')

        self.String = open(Configuration.path + 'String-nodes.csv', 'w+', buffering=1, encoding='utf-8', newline='')

        self.Data = open(Configuration.path + 'Data-relationships.csv', 'w+', buffering=1, encoding='utf-8', newline='')

        self.types = {
            'BinaryView': self.BinaryView, 'Function': self.Function, 'BasicBlock': self.BasicBlock,
            'Instruction': self.Instruction, 'Expression': self.Expression, 'Variable': self.Variable,
            'MemberFunc': self.MemberFunc, 'Calls': self.Calls, 'MemberBB': self.MemberBB, 'MemberBV': self.MemberBV,
            'VarOperand': self.VarOperand, 'Constant': self.Constant, 'ConstantOperand': self.ConstantOperand,
            'Operand': self.Operand, 'BreakDown': self.BreakDown, 'NextInstruction': self.NextInstruction,
            'InstructionChain': self.InstructionChain, 'Branch': self.Branch, 'String': self.String, 'Data': self.Data,
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

    def csv_dict_row_iterator(self, internal_type: str):
        """
        :param internal_type: The internal type of the object, this determines the csv file to open (taken from self.types)
        :return: return an iterator object that iterates on the rows of the CSV according to the field names
        """
        if internal_type in self.types:
            csvfile = self.types[internal_type]
            csvfile.seek(0)
            return csv.DictReader(csvfile)
        else:
            print("Wrong type argument given, no such internal type: ", type)

    def close_file_handles(self):
        for file in self.types.values():
            file.close()
