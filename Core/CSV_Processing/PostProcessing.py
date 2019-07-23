from ..Common import ContextManagement
from ..extraction_helpers import ProgramSymbol, String, CallSite, UseDef
from binaryninja import *


class CSVPostProcessor:
    # This class is responsible for enriching the information within the basic CSV files that
    # were created by BuildCSV.py.

    # TODO: refactor this whole class to be more efficient using the 'mandatory_context_dict'

    string_cache = dict()
    symbol_cache = dict()

    def __init__(self, bv: binaryview.BinaryView, CSV_Serializer):
        self.CSV_Serializer = CSV_Serializer
        self.bv = bv

    def run_all(self):
        #self.add_call_relationships()
        self.create_use_def_chain()

    def create_use_def_chain(self):
        # Create a relationship from an instruction node to the variable that it defines and\or uses.
        # Relationship type is either 'Uses' or 'Defines'.

        # Iterators over CSV files
        var_operand_relationship_iterator = self.CSV_Serializer.csv_dict_row_iterator('VarOperand')
        instruction_chain_relationship_iterator = self.CSV_Serializer.csv_dict_row_iterator('InstructionChain')
        next_instruction_relationship_iterator = self.CSV_Serializer.csv_dict_row_iterator('NextInstruction')

        # Cache dictionaries to speed up searches
        function_instruction_index_to_instruction_hash = dict()
        context_hash_cache = dict()

        # Init cache
        for row in next_instruction_relationship_iterator:
            # The cache uses the function uuid appended by the instruction index to speedup the search process
            function_instruction_index_to_instruction_hash.update({
                row['RootFunction'] + row['RootBasicBlock'] + row['InstructionIndex']: row['END_ID']
            })
        for row in instruction_chain_relationship_iterator:
            # The cache uses the function uuid appended by the instruction index to speedup the search process
            function_instruction_index_to_instruction_hash.update({
                row['RootFunction'] + row['RootBasicBlock'] + row['InstructionIndex']: row['END_ID']
            })

        # Iterate all variables and find the mlil_instruction index of their def\use
        for row in var_operand_relationship_iterator:
            usedef_context = ContextManagement.Context(row['RootBinaryView'], row['RootFunction'], row['RootBasicBlock'],
                                                row['RootInstruction'], row['RootExpression'])

            usedef_context.set_parent_hash(row['END_ID'])

            variable_definition_instruction_index_list = row['VariableDefinedAtIndex'].split(',')
            variable_use_instruction_index_list = row['VariableUsedAtIndex'].split(',')

            for instruction_index in variable_definition_instruction_index_list:
                instruction_hash = function_instruction_index_to_instruction_hash.get(
                    row['RootFunction'] + row['RootBasicBlock'] + instruction_index.strip())

                if instruction_hash:
                    usedef_context.set_hash(instruction_hash)

                    if context_hash_cache.get(usedef_context.context_hash()):
                        # Already defined this relationship in another code path, just skip it
                        pass
                    else:
                        def_chain_object = UseDef.Neo4jUseDef(usedef_context, 'DefinedAt')
                        self.CSV_Serializer.serialize_object(def_chain_object.serialize(), write_node=False,
                                                             write_relationship=True)
                        context_hash_cache.update(
                            {
                                usedef_context.context_hash(): True
                            }
                        )
                else:
                    pass
                    # print("Failed to locate definition of variable: ", row['END_ID'])

            for instruction_index in variable_use_instruction_index_list:
                instruction_hash = function_instruction_index_to_instruction_hash.get(
                    row['RootFunction'] + row['RootBasicBlock'] + instruction_index.strip())

                if instruction_hash:
                    usedef_context.set_hash(instruction_hash)

                    if context_hash_cache.get(usedef_context.context_hash()):
                        # Already defined this relationship in another code path, just skip it
                        pass
                    else:
                        def_chain_object = UseDef.Neo4jUseDef(usedef_context, 'UsedAt')
                        self.CSV_Serializer.serialize_object(def_chain_object.serialize(), write_node=False,
                                                             write_relationship=True)
                        context_hash_cache.update(
                            {
                                usedef_context.context_hash(): True
                            }
                        )

    def add_call_relationships(self):

        # Create helper CSV iterators
        expression_iterator = self.CSV_Serializer.csv_dict_row_iterator('Expression')
        operand_relationship_iterator = self.CSV_Serializer.csv_dict_row_iterator('Operand')
        constant_iterator = self.CSV_Serializer.csv_dict_row_iterator('Constant')
        constant_operand_relationship_iterator = self.CSV_Serializer.csv_dict_row_iterator('ConstantOperand')
        member_func_relationship_iterator = self.CSV_Serializer.csv_dict_row_iterator('MemberFunc')

        # define cache
        expression_cache = dict()
        operand_relationship_cache = dict()
        constant_cache = dict()
        constant_operand_relationship_cache = dict()
        member_func_relationship_cache = dict()

        # init cache
        for row in expression_iterator:
            expression_cache.update({row['HASH']: row})

        for row in constant_iterator:
            constant_cache.update({row['HASH']: row})

        for row in operand_relationship_iterator:
            if row['OperandIndex'] == '1':
                # Only the first operand of MLIL_CALL expression intrests us, as it holds the address of the callee
                operand_relationship_cache.update({row['START_ID']: row})

        for row in constant_operand_relationship_iterator:
            constant_operand_relationship_cache.update({row['START_ID']: row['END_ID']})

        for row in member_func_relationship_iterator:
            member_func_relationship_cache.update({row['Offset']: row['END_ID']})

        for row in self.CSV_Serializer.csv_dict_row_iterator('Expression'):
            # Iterate all expressions to locate the function calls
            if row['OperationName'] == 'MLIL_CALL':
                expression_first_operand = operand_relationship_cache.get(row['HASH'])
                callee_address_expression = expression_cache.get(expression_first_operand['END_ID'])
                if callee_address_expression:
                    if callee_address_expression['OperationName'] == 'MLIL_CONST_PTR':
                        constant_expression = constant_cache.get(
                            constant_operand_relationship_cache.get(
                                callee_address_expression['HASH']
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

