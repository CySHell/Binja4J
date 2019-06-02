from ..extraction_helpers import Symbol, String, CallSite


class PostProcessor:
    # This class is responsible for enriching the information within the basic CSV files that
    # were created by BuildCSV.py.

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
        binaryView_node_UUID = list(self.CSV_Serializer.csv_dict_row_iterator('BinaryView'))[0]['UUID']

        for symbol in self.bv.symbols.values():
            symbol_mapping.update({str(symbol.address): symbol})

        for row in constant_nodes_iterator:
            symbol = symbol_mapping.get(str(row['ConstantValue']))
            if symbol:
                symbol_object = Symbol.Neo4jSymbol(symbol, self.uuid_generator.get_uuid(),
                                                   row['UUID'], row['LABEL'],
                                                   binaryView_node_UUID)
                hash_exists = self.symbol_cache.get(symbol_object.HASH)

                if not hash_exists:
                    success = self.CSV_Serializer.serialize_object(symbol_object.serialize())
                    if success:
                        self.symbol_cache.update({symbol_object.HASH: str(symbol_object.UUID)})
                else:
                    symbol_object = Symbol.Neo4jSymbol(symbol, hash_exists, row['UUID'],
                                                       row['LABEL'],
                                                       binaryView_node_UUID)
                    self.CSV_Serializer.serialize_object(symbol_object.serialize(), write_node=False,
                                                         write_relationship=True)

    def add_call_relationships(self):

        # Iterators over CSV files
        expression_iterator = self.CSV_Serializer.csv_dict_row_iterator('Expression')
        operand_relationship_iterator = self.CSV_Serializer.csv_dict_row_iterator('Operand')
        constant_iterator = self.CSV_Serializer.csv_dict_row_iterator('Constant')
        constantOperand_relationship_iterator = self.CSV_Serializer.csv_dict_row_iterator('ConstantOperand')
        symbolRef_relationship_iterator = self.CSV_Serializer.csv_dict_row_iterator('SymbolRef')
        member_func_iterator = self.CSV_Serializer.csv_dict_row_iterator('MemberFunc')

        # Cache dictionaries to speed up searches
        callsite_expression_uuid_list = []
        operand_relationship_cache = dict()
        constantOperand_relationship_cache = dict()
        symbolRef_relationship_cache = dict()
        reverse_operand_relationship_cache = dict()

        # Helper mappings
        constant_uuid_to_value = dict()
        function_address_to_uuid = dict()
        expression_uuid_to_operation = dict()

        # The chain of nodes describing a call to a function is:
        # (:Instruction)-[:Operand {OperandIndex: '0']->
        # (:Expression {OperationName: 'MLIL_CALL')-[:Operand]->
        # (:Expression {OperationName: 'MLIL_CONST'|'MLIL_CONST_PTR'})-[ConstantOperand]->
        # (:Constant {ConstantValue: <>}) ?-[:SymbolRef]-> (:Symbol)

        # init Caches
        for row in operand_relationship_iterator:
            operand_relationship_cache.update({row['START_ID']: row})
            # This cache is responsible for mapping the expression node back to the original instruction node
            reverse_operand_relationship_cache.update({row['END_ID']: row})

        for row in constantOperand_relationship_iterator:
            constantOperand_relationship_cache.update({row['START_ID']: row})

        for row in symbolRef_relationship_iterator:
            symbolRef_relationship_cache.update({row['START_ID']: row})

        for row in constant_iterator:
            constant_uuid_to_value.update({row['UUID']: row['ConstantValue']})

        for row in member_func_iterator:
            function_address_to_uuid.update({row['Offset']: row['END_ID']})

        # Map each call instruction node to the corresponding function being called.

        for row in expression_iterator:
            if row['OperationName'] == 'MLIL_CALL':
                callsite_expression_uuid_list.append(row['UUID'])
            else:
                expression_uuid_to_operation.update({row['UUID']: row['OperationName']})

        for callsite_expression_uuid in callsite_expression_uuid_list:
            operand_relationship_call_target_expression_node = operand_relationship_cache.get(callsite_expression_uuid)
            callsite_instruction = reverse_operand_relationship_cache.get(callsite_expression_uuid)

            # MLIL_CALL first operand is the argument describing the address of the function being called
            if operand_relationship_call_target_expression_node['OperandIndex'] == '1':
                constant_node = constantOperand_relationship_cache.get(operand_relationship_call_target_expression_node['END_ID'])
                if constant_node:
                    constant_node_uuid = constant_node['END_ID']
                    constant_value = constant_uuid_to_value.get(constant_node_uuid)
                    called_function_uuid = function_address_to_uuid.get(constant_value)

                    if called_function_uuid:
                        callsite_object = CallSite.Neo4jCallSite(callsite_instruction['START_ID'], called_function_uuid)
                        self.CSV_Serializer.serialize_object(callsite_object.serialize(), write_node=False,
                                                             write_relationship=True)
                    else:
                        # TODO: constant_value is usually pointing to the IAT\GOT directly (in the data section),
                        #       so no function address is recognized.
                        #       Add code to handle this.
                        pass
                else:
                    # TODO: if constant_node doesn't exist, it means we are dealing with an indirect function
                    #       call, and the calling function is specified by an MLIL_VAR.
                    #       Add code to handle this situation.
                    pass
