"""
this module contains all the procedures for extracting data from a binary ninja binary view.
"""

from ..extraction_helpers import BinaryView, Function, BasicBlock, Instruction, Expression, Constant, \
    Variable, String, ProgramSymbol, CallSite

from . import CSV_Helper, PostProcessing

from ... import Configuration

from ..Common import ContextManagement

import time


class BinjaGraph:
    #   The BinjaGraph object holds the export_bv functionality of the whole plugin:
    #   1. Traverse the BinaryView and map all the objects to several CSV files
    #   2. Determine the relationships between all objects in the BinaryView
    #   3. Collect any additional information requested by the analysis_database_user
    #      from each object (via the /extraction_helpers)

    def __init__(self, driver, bv: BinaryView.BinaryView):
        """
        :param driver: The Neo4jBoltDriver object, facilitates communication with the DB
        :param uuid_generator: Provides UUID's for newly created objects
        :param bv: BinaryNinja BinaryView object, all information is extracted from this object
        """
        self.driver = driver
        self.bv = bv
        self.CSV_serializer = CSV_Helper.CSV_Serialize()
        self.bv_object = BinaryView.Neo4jBinaryView(self.bv)

        self.object_cache = dict({
            'BinaryView': dict(), 'Function': dict(), 'BasicBlock': dict(),
            'Instruction': dict(), 'Expression': dict(), 'Variable': dict(),
            'Constant': dict(), 'String': dict(), 'ProgramSymbol': dict(),
            'CallSite': dict(),
        }
        )

        # A dict of all context hashes already inserted into the object_cache
        self.context_hash_cache = dict()

        self.string_mapping = dict()
        for string in self.bv.strings:
            self.string_mapping.update({str(string.start): str(string.value)})

        self.symbol_mapping = dict()
        for program_symbol in self.bv.symbols.values():
            self.symbol_mapping.update({str(program_symbol.address): program_symbol})

    def bv_extract(self):
        """
        populate the graph with relevant info from the bv itself
        """

        self.update_object_cache('BinaryView', self.bv_object, True, True)

        start_time = time.time()
        # Iterate all functions in the BinaryView
        for func in self.bv:
            if len(func.mlil.basic_blocks) >= Configuration.MIN_MLIL_BASIC_BLOCKS:
                self.func_extract(func, self.bv_object)
        end_time = time.time()
        print("Finished defining function AST in ", end_time - start_time, " seconds")

        # Define function calls (instruction to function objects)
        self.def_function_calls()

        # object_cache structure example:
        # {'Function':
        #       {
        #        function_hash: [{
        #                         'Attributes': object_attributes (I.E object.serialize()),
        #                         'WriteNode': write_node,
        #                         'WriteRelationship': write_relationship
        #                         },
        #                         .....]

        for label in self.object_cache:
            for object_hash in self.object_cache[label].values():
                for object_entity in object_hash:
                    self.CSV_serializer.serialize_object(object_entity['Attributes'],
                                                         object_entity['WriteNode'],
                                                         object_entity['WriteRelationship'])

        post_processor = PostProcessing.CSVPostProcessor(self.bv, self.CSV_serializer)
        post_processor.run_all()
        self.CSV_serializer.close_file_handles()

    def func_extract(self, func, bv_object):
        """
        :param func: BinaryNinja RootFunction object to parse
        :param bv_uuid: UUID of the containing BinaryView
        """

        # Create the context for this function
        function_context = ContextManagement.Context(bv_object.context.SelfHASH)

        func_object = Function.Neo4jFunction(func.mlil, function_context)
        function_context.set_parent_hash(bv_object.context.SelfHASH)

        if function_context.SelfHASH in self.object_cache['Function']:
            # Function object already exists in the cache, only create the relationship (not the node itself)
            # and connect it with the existing node, then continue analysis of the function contents
            self.update_object_cache('Function', func_object, False, True)

        else:
            self.update_object_cache('Function', func_object, True, True)

        bb_control_flow_graph = [{'BasicBlockBinjaObject': func.mlil.basic_blocks[0],
                                  'BranchCondition': 0,
                                  'Context': function_context,
                                  'ParentHash': function_context.SelfHASH
                                  }]
        processed_bb_list = []

        # Iterate over all basic blocks in the Function and create the relationships
        # between them according to the control flow graph (I.E with branches between basic blocks)
        current_bb = bb_control_flow_graph.pop()

        while current_bb:
            bb_list, bb_object = self.bb_extract(current_bb['BasicBlockBinjaObject'],
                                                 current_bb['BranchCondition'],
                                                 current_bb['Context'],
                                                 current_bb['ParentHash'])
            for bb in bb_list:
                if bb in processed_bb_list:
                    bb_list.remove(bb)

            if bb_list:
                bb_control_flow_graph.extend(bb_list)
                processed_bb_list.extend(bb_list)

            if bb_control_flow_graph:
                current_bb = bb_control_flow_graph.pop()

            else:
                current_bb = False

    def bb_extract(self, basic_block, branch_condition: bool,
                   parent_context: ContextManagement.Context, parent_node_hash: str):
        """
        :param parent_node_hash:
        :param basic_block: BinaryNinja basic block object to parse
        :param branch_condition: branch condition to get to this basic block (0 = Unconditional, 1 = False, 2 = True)
        :param parent_context: the current RootFunction context we are working on
        :return: outgoing_edges_list: (LIST) a list of all the branches from this basic block that still need parsing
        """

        basic_block_context = ContextManagement.Context(parent_context.RootBinaryView,
                                                        # If parent node is a function it will not have a RootFunction,
                                                        # otherwise if its a basicblock then it does have RootFunction.
                                                        parent_context.RootFunction or parent_context.SelfHASH)
        basic_block_context.set_parent_hash(parent_node_hash)
        bb_object = BasicBlock.Neo4jBasicBlock(basic_block, branch_condition, basic_block_context)

        if basic_block_context.SelfHASH in self.object_cache['BasicBlock']:
            if self.context_hash_cache.get(basic_block_context.context_hash()):
                # This basic block was already explored by a different path through the function (since it has the same
                # context hash), just skip it completely
                return list(), None
            else:
                # BasicBlock object already exists in the cache, only create the relationship (not the node itself)
                # and connect it with the existing node, then continue analysis of the BasicBlock contents
                self.update_object_cache('BasicBlock', bb_object, False, True)
        else:
            self.update_object_cache('BasicBlock', bb_object, True, True)

        # build the RootInstruction chain under the BB
        parent_node_hash = basic_block_context.SelfHASH
        p_node_type = 'BasicBlock'
        for instruction in basic_block:
            parent_node_hash = self.instruction_extract(instruction, basic_block_context, parent_node_hash, p_node_type)
            p_node_type = 'Instruction'

        outgoing_edges_list = []
        # Iterate all branches of the current basic block and create them
        for branch in basic_block.outgoing_edges:
            if branch.back_edge is False:
                # if the branch isn't a back_edge just add it to the list to be processed in the future
                branch_struct = {'BasicBlockBinjaObject': branch.target,
                                 'BranchCondition': branch.type.value,
                                 'Context': basic_block_context,
                                 'ParentHash': basic_block_context.SelfHASH}
                outgoing_edges_list.append(branch_struct)
            else:
                # branch is a back_edge, so the basic_block it points to already exists.
                # just create the relationship between the two existing basic blocks, no new node additions
                back_edge_context = ContextManagement.Context(basic_block_context.RootBinaryView,
                                                              basic_block_context.RootFunction)
                back_edge_context.set_parent_hash(basic_block_context.SelfHASH)

                back_edge_object = BasicBlock.Neo4jBasicBlock(branch.target, branch.type.value, back_edge_context,
                                                              back_edge=True)
                self.update_object_cache('BasicBlock', back_edge_object, False, True)

        return outgoing_edges_list, bb_object

    def instruction_extract(self, instruction, basic_block_context: ContextManagement.Context, parent_node_hash,
                            parent_node_type):
        """
        :param instruction: BinaryNinja MLIL Instruction object
        :param basic_block_context
        :param parent_node_hash
        :return: (int): the UUID of the newly created RootInstruction object
        """

        instruction_context = ContextManagement.Context(basic_block_context.RootBinaryView,
                                                        basic_block_context.RootFunction,
                                                        basic_block_context.SelfHASH
                                                        )

        instruction_context.set_parent_hash(parent_node_hash)
        instr_object = Instruction.Neo4jInstruction(instruction, instruction_context, parent_node_type)

        if instruction_context.SelfHASH in self.object_cache['Instruction']:
            if self.context_hash_cache.get(instruction_context.context_hash()):
                # We already encountered this instruction via another code path (same context), so no need to
                # re-create it.
                return instruction_context.SelfHASH
            else:
                # BasicBlock object already exists in the cache, only create the relationship (not the node itself)
                # and connect it with the existing node, then continue analysis of the BasicBlock contents
                self.update_object_cache('Instruction', instr_object, False, True)
        else:
            self.update_object_cache('Instruction', instr_object, True, True)

        # Each RootInstruction is further extracted into an RootExpression (like an AST)
        self.expression_extract(instruction, instruction_context, 0, parent_node_type='Instruction')

        return instruction_context.SelfHASH

    def expression_extract(self, instruction, parent_context: ContextManagement.Context, operand_index,
                           parent_node_type='Expression'):
        """
        An RootExpression is a breakdown of an MLIL RootInstruction into its individual operands under a single
        operation
        :param instruction: BinaryNinja MLIL Insutrction object
        :param parent_context
        :param operand_index: (INT) index of the RootExpression within the parent RootInstruction or RootExpression
                                    operand list
        :param parent_node_hash
        :param parent_node_type: (STR) parent of an RootExpression can be either an RootInstruction or an RootExpression
        """
        expression_context = ContextManagement.Context(
            parent_context.RootBinaryView,
            parent_context.RootFunction,
            parent_context.RootBasicBlock,
            # If the parent is an instruction then RootInstruction is empty,
            # just use the instruction SelfHASH instead
            parent_context.RootInstruction if parent_node_type == 'Expression' else parent_context.SelfHASH,
            parent_context.RootExpression,
            operand_index,
        )

        if parent_node_type == 'Expression':
            expression_context.RootExpression = parent_context.SelfHASH

        expression_context.set_parent_hash(parent_context.SelfHASH)

        expr_object = Expression.Neo4jExpression(instruction, expression_context, parent_node_type)

        if expression_context.SelfHASH in self.object_cache['Expression']:
            if self.context_hash_cache.get(expression_context.context_hash()):
                return
            else:
                # Expression object already exists in the cache, only create the relationship (not the node itself)
                # and connect it with the existing node, then continue analysis of the Expression contents
                self.update_object_cache('Expression', expr_object, False, True)
        else:
            self.update_object_cache('Expression', expr_object, True, True)

        # Iterate the operand list according to the object types specified in the MLIL_Operations enum
        index = 0
        for op_description in instruction.ILOperations[instruction.operation]:
            op_description_type = op_description[1]

            if op_description_type == 'expr':
                self.expression_extract(instruction.operands[index], expression_context, index)
                index += 1
                continue
            if op_description_type == 'var':
                self.var_extract(instruction.operands[index],
                                 index, expression_context)
                index += 1
                continue
            if op_description_type == 'expr_list':
                expression_index = 0
                for expr in instruction.operands[index]:
                    self.expression_extract(expr, expression_context, 'func_param_' + str(expression_index))
                    expression_index += 1
                index += 1
                continue
            if op_description_type == 'var_list':
                var_index = 0
                for il_variable in instruction.operands[index]:
                    self.var_extract(il_variable, var_index, expression_context)
                    var_index += 1
                index += 1
                continue
            if op_description_type == 'int':
                self.constant_extract(instruction.operands[index],
                                      index, expression_context)
                index += 1
                continue
            if op_description_type == 'int_list':
                print("Encountered an int_list operation at ", index, ": ", instruction)
                # TODO: implement this
                index += 1
                continue
            if op_description_type == 'float':
                self.constant_extract(instruction.operands[index],
                                      index, expression_context)
                index += 1
                continue
            if op_description_type == 'var_ssa':
                print("Encountered a var_ssa operation at ", index, ": ", instruction)
                # TODO: implement this
                index += 1
                continue
            if op_description_type == 'var_ssa_dest_and_src':
                print("Encountered a var_ssa_dest_and_src operation at ", index, ": ", instruction)
                # TODO: implement this
                index += 1
                continue
            if op_description_type == 'var_ssa_list':
                print("Encountered a var_ssa_list operation at ", index, ": ", instruction)
                # TODO: implement this
                index += 1
                continue
            if op_description_type == 'intrinsic':
                print("Encountered an intrinsic operation at ", index, ": ", instruction)
                # TODO: implement this
                index += 1
                continue
            print("op_description_type un-parsed:", op_description)
            index += 1

    def var_extract(self, var, index: int, context: ContextManagement.Context):
        """
        :param var: BinaryNinja MLIL_VAR object
        :param uuid: UUID to give this VAR object within the CSV
        :param index: operand index of this var within the parent RootExpression operand list
        :param parent_expr_uuid
        :param context
        """

        variable_context = ContextManagement.Context(context.RootBinaryView, context.RootFunction,
                                                     context.RootBasicBlock, context.RootInstruction,
                                                     # If the parent is a root expression (as opposed to a
                                                     # sub-expression) then RootExpression is empty.
                                                     # just use the instruction SelfHASH instead.
                                                     context.RootExpression or context.SelfHASH,
                                                     index)

        variable_context.set_parent_hash(context.SelfHASH)

        var_object = Variable.Neo4jVar(var, index, variable_context)

        if variable_context.SelfHASH in self.object_cache['Variable']:
            if self.context_hash_cache.get(variable_context.context_hash()):
                return
            else:
                # Expression object already exists in the cache, only create the relationship (not the node itself)
                # and connect it with the existing node, then continue analysis of the Expression contents
                self.update_object_cache('Variable', var_object, False, True)
        else:
            self.update_object_cache('Variable', var_object, True, True)

    def constant_extract(self, constant, index: int, context: ContextManagement.Context):
        """
        :param constant: A constant value (e.g "54343")
        :param uuid: UUID to assign to this constant
        :param index: index of the constant within the parent RootExpression operand list
        :param context
        """
        constant_context = ContextManagement.Context(context.RootBinaryView, context.RootFunction,
                                                     context.RootBasicBlock, context.RootInstruction,
                                                     # If the parent is a root expression (as opposed to a
                                                     # sub-expression) then RootExpression is empty.
                                                     # just use the instruction SelfHASH instead.
                                                     context.RootExpression or context.SelfHASH,
                                                     index)

        constant_context.set_parent_hash(context.SelfHASH)

        const_object = Constant.Neo4jConstant(constant, index, constant_context)

        if constant_context.SelfHASH in self.object_cache['Constant']:
            if self.context_hash_cache.get(constant_context.context_hash()):
                return
            else:
                # Expression object already exists in the cache, only create the relationship (not the node itself)
                # and connect it with the existing node, then continue analysis of the Expression contents
                self.update_object_cache('Constant', const_object, False, True)
        else:
            self.update_object_cache('Constant', const_object, True, True)

        raw_string = self.string_mapping.get(str(constant))
        if raw_string:
            # This constant is a pointer to a string, we need to create the string object
            self.string_extract(raw_string, constant_context)

        raw_symbol = self.symbol_mapping.get(str(constant))
        if raw_symbol:
            # This constant represents a program symbol, we need to create the string object
            self.symbol_extract(raw_symbol, constant_context)

    def string_extract(self, raw_string: str, context):
        string_context = ContextManagement.Context(context.RootBinaryView, context.RootFunction,
                                                   context.RootBasicBlock, context.RootInstruction,
                                                   context.RootExpression)

        string_context.set_parent_hash(context.SelfHASH)

        string_object = String.Neo4jString(raw_string, string_context)

        if string_context.SelfHASH in self.object_cache['String']:
            if self.context_hash_cache.get(string_context.context_hash()):
                return
            else:
                self.update_object_cache('String', string_object, False, True)
        else:
            self.update_object_cache('String', string_object, True, True)

    def symbol_extract(self, raw_symbol: str, context):
        symbol_context = ContextManagement.Context(context.RootBinaryView, context.RootFunction,
                                                   context.RootBasicBlock, context.RootInstruction,
                                                   context.RootExpression)

        symbol_context.set_parent_hash(context.SelfHASH)

        symbol_object = ProgramSymbol.Neo4jSymbol(raw_symbol, symbol_context)

        if symbol_context.SelfHASH in self.object_cache['ProgramSymbol']:
            if self.context_hash_cache.get(symbol_context.context_hash()):
                return
            else:
                self.update_object_cache('ProgramSymbol', symbol_object, False, True)
        else:
            self.update_object_cache('ProgramSymbol', symbol_object, True, True)

    def update_object_cache(self, object_type: str, program_object, write_node, write_relationship):

        object_attributes = program_object.serialize()
        if not object_attributes['mandatory_context_dict']['SelfHASH'] in self.object_cache[object_type]:
            self.object_cache[object_type][object_attributes['mandatory_context_dict']['SelfHASH']] = list()

        self.object_cache[object_type][object_attributes['mandatory_context_dict']['SelfHASH']].append(
            {'Attributes': object_attributes, 'WriteNode': write_node, 'WriteRelationship': write_relationship})

        self.context_hash_cache.update({
            object_attributes['mandatory_context_dict']['ContextHash']: True
        }
        )

    def def_function_calls(self):

        function_offset_to_hash_cache = dict()
        expr_hash_to_first_argument_expr = dict()
        expr_hash_to_function_pointer = dict()

        for func in self.object_cache['Function'].values():
            for func_entity in func:
                func_offset = func_entity['Attributes']['mandatory_relationship_dict']['Offset']
                func_hash = func_entity['Attributes']['mandatory_context_dict']['SelfHASH']
                function_offset_to_hash_cache.update({
                    func_offset: func_hash
                })

        for expr in self.object_cache['Expression'].values():
            for expr_entity in expr:
                if expr_entity['Attributes']['mandatory_context_dict']['OperandIndex'] == '1':
                    # We are only interested in the first argument of the call instruction
                    expr_hash = expr_entity['Attributes']['mandatory_context_dict']['SelfHASH']
                    parent_expr_hash = expr_entity['Attributes']['mandatory_context_dict']['ParentHASH']
                    expr_hash_to_first_argument_expr.update({
                        parent_expr_hash: expr_hash
                    })

        for const in self.object_cache['Constant'].values():
            for const_entity in const:
                const_value = const_entity['Attributes']['mandatory_node_dict']['ConstantValue']
                parent_expr_hash = const_entity['Attributes']['mandatory_context_dict']['ParentHASH']
                expr_hash_to_function_pointer.update({
                    parent_expr_hash: const_value
                })

        for expr in self.object_cache['Expression'].values():
            for expr_entity in expr:
                if expr_entity['Attributes']['mandatory_node_dict']['OperationName'] == 'MLIL_CALL' or 'MLIL_TAILCALL':
                    first_argument_expr_hash = expr_hash_to_first_argument_expr.get(
                        expr_entity['Attributes']['mandatory_context_dict']['SelfHASH']
                    )
                    if first_argument_expr_hash:
                        function_offset = expr_hash_to_function_pointer.get(first_argument_expr_hash)
                        if function_offset:
                            function_hash = function_offset_to_hash_cache.get(function_offset)
                            if function_hash:
                                context_dict = expr_entity['Attributes']['mandatory_context_dict']
                                # Create the context of the call_site (same as the instruction context)
                                call_site_context = ContextManagement.Context(context_dict['RootBinaryView'],
                                                                              context_dict['RootFunction'],
                                                                              context_dict['RootBasicBlock'],
                                                                              context_dict['RootInstruction'])
                                call_site_context.set_parent_hash(call_site_context.RootInstruction)
                                call_site_context.set_hash(function_hash)

                                # Create the call_site_object and update the object_cache
                                call_site_object = CallSite.Neo4jCallSite(call_site_context)
                                self.update_object_cache('CallSite', call_site_object, False, True)
                            else:
                                pass
                                # print("Failed to locate function hash for function offset: ", function_offset)
                        else:
                            pass
                            # print("Failed to locate function offset in expr hash: ", first_argument_expr_hash)
                    else:
                        pass
                        # print("Failed to locate the first argument expression for expr hash: ",
                        #      expr_entity['Attributes']['mandatory_context_dict']['SelfHASH'])
