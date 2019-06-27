from ..Common import ContextManagement
from ..extraction_helpers import ProgramSymbol, String, CallSite, UseDef
from binaryninja import *


class CSVPostProcessor:
    # This class is responsible for enriching the information within the basic CSV files that
    # were created by BuildCSV.py.

    # TODO: refactor this whole class to be more efficient using the 'mandatory_context_dict'

    string_cache = dict()
    symbol_cache = dict()

    def __init__(self, bv, CSV_Serializer, uuid_generator, cache):
        self.CSV_Serializer = CSV_Serializer
        self.bv = bv
        self.binaryView_node_UUID = list(self.CSV_Serializer.csv_dict_row_iterator('BinaryView'))[0]['UUID']
        self.uuid_generator = uuid_generator
        self.cache = cache

    def run_all(self):
        self.add_strings()
        self.add_symbols()
        self.add_call_relationships()
        self.create_use_def_chain()

    def add_strings(self):
        string_mapping = {}

        constant_nodes_iterator = self.CSV_Serializer.csv_dict_row_iterator('Constant')

        for string in self.bv.strings:
            string_mapping.update({str(string.start): str(string.value)})

        for row in constant_nodes_iterator:
            raw_string = string_mapping.get(str(row['ConstantValue']))
            if raw_string:
                string_object = String.Neo4jString(raw_string, self.uuid_generator.get_uuid(), row['UUID'],
                                                   row['LABEL'],
                                                   self.binaryView_node_UUID)
                hash_exists = self.string_cache.get(string_object.HASH)

                if not hash_exists:
                    success = self.CSV_Serializer.serialize_object(string_object.serialize())
                    if success:
                        self.string_cache.update({string_object.HASH: str(string_object.UUID)})
                else:
                    string_object = String.Neo4jString(raw_string, hash_exists, row['UUID'], row['LABEL'],
                                                       self.binaryView_node_UUID)
                    self.CSV_Serializer.serialize_object(string_object.serialize(), write_node=False,
                                                         write_relationship=True)

    def add_symbols(self):
        symbol_mapping = {}

        constant_nodes_iterator = self.CSV_Serializer.csv_dict_row_iterator('Constant')

        for symbol in self.bv.symbols.values():
            symbol_mapping.update({str(symbol.address): symbol})

        for row in constant_nodes_iterator:
            symbol = symbol_mapping.get(str(row['ConstantValue']))
            if symbol:
                symbol_object = ProgramSymbol.Neo4jSymbol(symbol, self.uuid_generator.get_uuid(),
                                                          row['UUID'], row['LABEL'],
                                                          self.binaryView_node_UUID)
                hash_exists = self.symbol_cache.get(symbol_object.HASH)

                if not hash_exists:
                    success = self.CSV_Serializer.serialize_object(symbol_object.serialize())
                    if success:
                        self.symbol_cache.update({symbol_object.HASH: str(symbol_object.UUID)})
                else:
                    symbol_object = ProgramSymbol.Neo4jSymbol(symbol, hash_exists, row['UUID'],
                                                              row['LABEL'],
                                                              self.binaryView_node_UUID)
                    self.CSV_Serializer.serialize_object(symbol_object.serialize(), write_node=False,
                                                         write_relationship=True)

    def create_use_def_chain(self):
        # Create a relationship from an instruction node to the variable that it defines and\or uses.
        # Relationship type is either 'Uses' or 'Defines'.

        # Iterators over CSV files
        var_operand_relationship_iterator = self.CSV_Serializer.csv_dict_row_iterator('VarOperand')
        instruction_chain_relationship_iterator = self.CSV_Serializer.csv_dict_row_iterator('InstructionChain')
        next_instruction_relationship_iterator = self.CSV_Serializer.csv_dict_row_iterator('NextInstruction')

        # Cache dictionaries to speed up searches
        function_instruction_index_to_instruction_uuid = dict()

        # Init cache
        for row in next_instruction_relationship_iterator:
            # The cache uses the function uuid appended by the instruction index to speedup the search process
            function_instruction_index_to_instruction_uuid.update({
                row['RootFunction'] + row['InstructionIndex']: row['END_ID']
            })
        for row in instruction_chain_relationship_iterator:
            # The cache uses the function uuid appended by the instruction index to speedup the search process
            function_instruction_index_to_instruction_uuid.update({
                row['RootFunction'] + row['InstructionIndex']: row['END_ID']
            })

        # Iterate all variables and find the mlil_instruction index of their def\use
        for row in var_operand_relationship_iterator:
            context = ContextManagement.Context(row['RootBinaryView'], row['RootFunction'], row['RootBasicBlock'],
                                                row['RootInstruction'])
            root_function = row['RootFunction']
            variable_uuid = row['END_ID']
            variable_definition_instruction_index_list = row['VariableDefinedAtIndex'].split(',')
            variable_use_instruction_index_list = row['VariableUsedAtIndex'].split(',')

            for instruction_index in variable_definition_instruction_index_list:
                instruction_uuid = function_instruction_index_to_instruction_uuid.get(
                    root_function + str(instruction_index))

                def_chain_object = UseDef.Neo4jUseDef(variable_uuid, instruction_uuid, context, 'DefinedAt')
                self.CSV_Serializer.serialize_object(def_chain_object.serialize(), write_node=False,
                                                     write_relationship=True)

            for instruction_index in variable_use_instruction_index_list:
                instruction_uuid = function_instruction_index_to_instruction_uuid.get(
                    root_function + str(instruction_index))

                def_chain_object = UseDef.Neo4jUseDef(variable_uuid, instruction_uuid, context, 'UsedAt')
                self.CSV_Serializer.serialize_object(def_chain_object.serialize(), write_node=False,
                                                     write_relationship=True)

    def add_call_relationships(self):

        # Create helper CSV iterators
        expression_iterator = self.CSV_Serializer.csv_dict_row_iterator('Expression')
        operand_relationship_iterator = self.CSV_Serializer.csv_dict_row_iterator('Operand')
        constant_iterator = self.CSV_Serializer.csv_dict_row_iterator('Constant')
        constantOperand_relationship_iterator = self.CSV_Serializer.csv_dict_row_iterator('ConstantOperand')
        member_func_relationship_iterator = self.CSV_Serializer.csv_dict_row_iterator('MemberFunc')

        # define cache
        expression_cache = dict()
        operand_relationship_cache = dict()
        constant_cache = dict()
        constantOperand_relationship_cache = dict()
        member_func_relationship_cache = dict()

        # init cache
        for row in expression_iterator:
            expression_cache.update({row['UUID']: row})

        for row in constant_iterator:
            constant_cache.update({row['UUID']: row})

        for row in operand_relationship_iterator:
            if row['OperandIndex'] == '1':
                # Only the first operand of MLIL_CALL expression intrests us, as it holds the address of the callee
                operand_relationship_cache.update({row['START_ID']: row})

        for row in constantOperand_relationship_iterator:
            constantOperand_relationship_cache.update({row['START_ID']: row['END_ID']})

        for row in member_func_relationship_iterator:
            member_func_relationship_cache.update({row['Offset']: row['END_ID']})

        for row in self.CSV_Serializer.csv_dict_row_iterator('Expression'):
            # Iterate all expressions to locate the function calls
            if row['OperationName'] == 'MLIL_CALL':
                expression_first_operand = operand_relationship_cache.get(row['UUID'])
                callee_address_expression = expression_cache.get(expression_first_operand['END_ID'])
                if callee_address_expression:
                    if callee_address_expression['OperationName'] == 'MLIL_CONST_PTR':
                        constant_expression = constant_cache.get(
                            constantOperand_relationship_cache.get(
                                callee_address_expression['UUID']
                            ))
                        if constant_expression:
                            callee_func_uuid = member_func_relationship_cache.get(constant_expression['ConstantValue'])
                            if callee_func_uuid:
                                context = ContextManagement.Context(expression_first_operand['RootBinaryView'],
                                                                    expression_first_operand['RootFunction'],
                                                                    expression_first_operand['RootBasicBlock'],
                                                                    expression_first_operand['RootInstruction'],
                                                                    expression_first_operand['RootExpression'])
                                callsite_object = CallSite.Neo4jCallSite(expression_first_operand['RootInstruction'],
                                                                         callee_func_uuid
                                                                         , context)
                                self.CSV_Serializer.serialize_object(callsite_object.serialize(), write_node=False,
                                                                     write_relationship=True)
                    else:
                        # TODO: if the mlil operation is something like 'MLIL_VAR' it means we have an idirect call.
                        #       Add heuristics to understand the function being pointed.
                        pass
