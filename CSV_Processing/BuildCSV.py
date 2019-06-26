"""
this module contains all the procedures for extracting data from a binary ninja binary view.
"""

from ..extraction_helpers import BinaryView, Function, BasicBlock, Instruction, Expression, Constant, \
    Variable

from . import CSV_Helper, PostProcessing

from ..Common import ContextManagement


class BinjaGraph:
    #   The BinjaGraph object holds the export_bv functionality of the whole plugin:
    #   1. Traverse the BinaryView and map all the objects to several CSV files
    #   2. Determine the relationships between all objects in the BinaryView
    #   3. Collect any additional information requested by the analysis_database_user
    #      from each object (via the /extraction_helpers)

    def __init__(self, driver, uuid_generator, bv):
        """
        :param driver: The Neo4jBoltDriver object, facilitates communication with the DB
        :param uuid_generator: Provides UUID's for newly created objects
        :param bv: BinaryNinja BinaryView object, all information is extracted from this object
        """
        self.driver = driver
        self.uuid_generator = uuid_generator
        self.bv = bv
        self.CSV_serializer = CSV_Helper.CSV_Serialize()

        # Caching objects to allow for faster CSV creation.
        # Each object is in the form of {HASH: UUID}

        self.function_cache = dict()
        self.basic_block_cache = dict()
        self.instruction_cache = dict()
        self.expression_cache = dict()
        self.var_cache = dict()
        self.const_cache = dict()
        self.branch_rel_cache = dict()

    def bv_extract(self):
        """
        populate the graph with relevant info from the bv itself
        """

        # Create a dictionary containing all relevant information for the graph node\relationship creation
        bv_object = BinaryView.Neo4jBinaryView(self.bv, self.uuid_generator.get_uuid())
        # Write the dictionary into the CSV file
        success = self.CSV_serializer.serialize_object(bv_object.serialize())
        if success:
            # Iterate all functions in the BinaryView
            for func in self.bv:
                self.func_extract(func, bv_object.UUID)

        cache = {
            'Function': self.function_cache,
            'BasicBlock': self.basic_block_cache,
            'Instruction': self.instruction_cache,
            'Expression': self.expression_cache,
            'Variable': self.var_cache,
            'Constant': self.const_cache,
        }
        post_processor = PostProcessing.CSVPostProcessor(self.bv, self.CSV_serializer, self.uuid_generator, cache)
        post_processor.run_all()

        self.CSV_serializer.close_file_handles()

    def func_extract(self, func, bv_uuid: str):
        """
        :param func: BinaryNinja RootFunction object to parse
        :param bv_uuid: UUID of the containing BinaryView
        """

        # Create the context object for everything under this RootFunction
        current_context = ContextManagement.Context(bv_uuid)

        func_object = Function.Neo4jFunction(func.mlil, self.uuid_generator.get_uuid(), current_context)

        hash_exists = self.function_cache.get(func_object.HASH)

        if not hash_exists:
            # The RootFunction doesn't already exist in the CSV

            # Update current context
            current_context.RootFunction = func_object.UUID

            success = self.CSV_serializer.serialize_object(func_object.serialize())
            bb_control_flow_graph = [(func.mlil.basic_blocks[0], 0, current_context.RootFunction)]
            processed_bb_list = []
            if success:

                # Iterate over all basic blocks in the RootFunction and create the relationships
                # between them according to the control flow graph (I.E with branches between basic blocks)
                current_bb = bb_control_flow_graph.pop()
                while current_bb:
                    current_context.RootBasicBlock = current_bb[2]
                    bb_list, _ = self.bb_extract(current_bb[0], current_bb[1], current_context)
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
        else:
            # Function object already exists in the CSV, only create the relationship (not the node itself)
            # and connect it with the existing node
            func_object = Function.Neo4jFunction(func.mlil, hash_exists, bv_uuid)
            self.CSV_serializer.serialize_object(func_object.serialize(), write_node=False, write_relationship=True)

    def bb_extract(self, basic_block, branch_condition: bool, context: ContextManagement.Context):
        """
        :param basic_block: BinaryNinja basic block object to parse
        :param branch_condition: branch condition to get to this basic block (0 = Unconditional, 1 = False, 2 = True)
        :param context: the current RootFunction context we are working on
        :return: outgoing_edges_list: (LIST) a list of all the branches from this basic block that still need parsing
        """
        bb_object = BasicBlock.Neo4jBasicBlock(basic_block, self.uuid_generator.get_uuid(), branch_condition, context)

        hash_exists = self.basic_block_cache.get(bb_object.NODE_HASH)

        if not hash_exists:
            success = self.CSV_serializer.serialize_object(bb_object.serialize())
            if success:
                # Update context
                context.RootBasicBlock = bb_object.UUID

                self.basic_block_cache.update({bb_object.NODE_HASH: str(bb_object.UUID)})
                self.branch_rel_cache.update({bb_object.RELATIONSHIP_HASH: True})

                # build the RootInstruction chain under the BB
                for instruction in basic_block:
                    context.RootInstruction = self.instruction_extract(instruction, context)
        else:
            bb_object = BasicBlock.Neo4jBasicBlock(basic_block, hash_exists, branch_condition, context)

            relationship_exists = self.branch_rel_cache.get(bb_object.RELATIONSHIP_HASH)

            if not relationship_exists:
                success = self.CSV_serializer.serialize_object(bb_object.serialize(),
                                                               write_node=False, write_relationship=True)
                if success:
                    # Update context and cache
                    context.RootBasicBlock = bb_object.UUID
                    self.branch_rel_cache.update({bb_object.RELATIONSHIP_HASH: True})

                    # create new relationships for the RootInstruction chain under the BB
                    for instruction in basic_block:
                        context.RootInstruction = self.instruction_extract(instruction, context)

        # Update context
        context.RootBasicBlock = bb_object.UUID

        outgoing_edges_list = []
        # Iterate all branches of the current basic block and create them
        for branch in basic_block.outgoing_edges:
            if branch.back_edge is False:
                # if the branch isn't a back_edge just add it to the list to be processed in the future
                branch_struct = [branch.target, branch.type.value, context.RootBasicBlock]
                outgoing_edges_list.append(branch_struct)
            else:
                # branch is a back_edge, so the basic_block it points to already exists.
                # just create the relationship between the two existing basic blocks, no new node additions
                target_bb_object = BasicBlock.Neo4jBasicBlock(branch.target, self.uuid_generator.get_uuid(),
                                                              branch.type.value, context, back_edge=True)
                hash_exists = self.basic_block_cache.get(target_bb_object.NODE_HASH)

                if not hash_exists:
                    # In the edge case that the basic block that is being branched to doesn't yet exist,
                    # create it immediately and continue with the branches.
                    # Todo: Find a more elegant way to deal with this case
                    _, target_bb_object = self.bb_extract(branch.target, branch.type.value, context)
                else:
                    # Must create correct representation of the existing BasicBlock
                    target_bb_object = BasicBlock.Neo4jBasicBlock(branch.target, hash_exists, branch.type.value,
                                                                  context, back_edge=True)

                relationship_exists = self.branch_rel_cache.get(target_bb_object.RELATIONSHIP_HASH)

                if not relationship_exists:
                    self.CSV_serializer.serialize_object(target_bb_object.serialize(), False, write_relationship=True)
                    self.branch_rel_cache.update({target_bb_object.RELATIONSHIP_HASH: True})

        return outgoing_edges_list, bb_object

    def instruction_extract(self, instruction, context: ContextManagement.Context):
        """
        :param instruction: BinaryNinja MLIL Instruction object
        :param context
        :return: (int): the UUID of the newly created RootInstruction object
        """

        instr_object = Instruction.Neo4jInstruction(instruction, self.uuid_generator.get_uuid(),
                                                    context)

        hash_exists = self.instruction_cache.get(instr_object.HASH)
        if not hash_exists:
            success = self.CSV_serializer.serialize_object(instr_object.serialize())
            if not success:
                print("Error writing Instruction object to CSV")
            else:
                # Update Context and cache
                context.RootInstruction = instr_object.UUID
                context.RootExpression = instr_object.UUID
                self.instruction_cache.update({instr_object.HASH: str(instr_object.UUID)})

                # Each RootInstruction is further extracted into an RootExpression (like an AST)
                self.expression_extract(instruction, context, 0, parent_node_type='Instruction')
        else:
            instr_object = Instruction.Neo4jInstruction(instruction, hash_exists,
                                                        context)
            self.CSV_serializer.serialize_object(instr_object.serialize(), write_node=False, write_relationship=True)

        return instr_object.UUID

    def expression_extract(self, instruction, context: ContextManagement.Context, operand_index,
                           parent_node_type='Expression'):
        """
        An RootExpression is a breakdown of an MLIL RootInstruction into its individual operands under a single
        operation
        :param instruction: BinaryNinja MLIL Insutrction object
        :param context
        :param operand_index: (INT) index of the RootExpression within the parent RootInstruction or RootExpression
                                    operand list
        :param parent_node_type: (STR) parent of an RootExpression can be either an RootInstruction or an RootExpression
        """
        expr_object = Expression.Neo4jExpression(instruction, self.uuid_generator.get_uuid(),
                                                 context, parent_node_type,
                                                 operand_index)

        hash_exists = self.expression_cache.get(expr_object.HASH)

        if not hash_exists:
            success = self.CSV_serializer.serialize_object(expr_object.serialize())
            if not success:
                print("Error writing Expression object to CSV: ")
            else:
                # Update context and cache
                context.RootExpression = expr_object.UUID
                self.expression_cache.update({expr_object.HASH: str(expr_object.UUID)})

                # Iterate the operand list according to the object types specified in the MLIL_Operations enum
                index = 0
                for op_description in instruction.ILOperations[instruction.operation]:
                    op_description_type = op_description[1]

                    if op_description_type == 'expr':
                        self.expression_extract(instruction.operands[index], context, index)
                        index += 1
                        continue
                    if op_description_type == 'var':
                        self.var_extract(instruction.operands[index], self.uuid_generator.get_uuid(),
                                         index, expr_object.UUID, context)
                        index += 1
                        continue
                    if op_description_type == 'expr_list':
                        expression_index = 0
                        for expr in instruction.operands[index]:
                            context.RootExpression = expr_object.UUID
                            self.expression_extract(expr, context, 'func_param_' + str(expression_index))
                            expression_index += 1
                        index += 1
                        continue
                    if op_description_type == 'var_list':
                        var_index = 0
                        for il_variable in instruction.operands[index]:
                            self.var_extract(il_variable, self.uuid_generator.get_uuid(), var_index, expr_object.UUID,
                                             context)
                            var_index += 1
                        index += 1
                        continue
                    if op_description_type == 'int':
                        self.constant_extract(instruction.operands[index], self.uuid_generator.get_uuid(),
                                              index, context)
                        index += 1
                        continue
                    if op_description_type == 'int_list':
                        # TODO: implement this
                        index += 1
                        continue
                    if op_description_type == 'float':
                        self.constant_extract(instruction.operands[index], self.uuid_generator.get_uuid(),
                                              index, context)
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
        else:
            # Expression already exists, only create the relationship between the existing nodes
            expr_object = Expression.Neo4jExpression(instruction, hash_exists,
                                                     context, parent_node_type,
                                                     operand_index)
            self.CSV_serializer.serialize_object(expr_object.serialize(), write_node=False, write_relationship=True)

    def var_extract(self, var, uuid: str, index: int, parent_expr_uuid: str, context: ContextManagement.Context):
        """
        :param var: BinaryNinja MLIL_VAR object
        :param uuid: UUID to give this VAR object within the CSV
        :param index: operand index of this var within the parent RootExpression operand list
        :param parent_expr_uuid
        :param context
        """

        var_object = Variable.Neo4jVar(var, uuid, index, parent_expr_uuid, context)
        hash_exists = self.var_cache.get(var_object.HASH)

        if not hash_exists:
            success = self.CSV_serializer.serialize_object(var_object.serialize())
            if not success:
                print("Error writing Var object to CSV")
            else:
                self.var_cache.update({var_object.HASH: str(var_object.UUID)})
        else:
            var_object = Variable.Neo4jVar(var, hash_exists,
                                           index, parent_expr_uuid, context)
            self.CSV_serializer.serialize_object(var_object.serialize(), write_node=False, write_relationship=True)

    def constant_extract(self, constant, uuid: str, index: int, context: ContextManagement.Context):
        """
        :param constant: A constant value (e.g "54343")
        :param uuid: UUID to assign to this constant
        :param index: index of the constant within the parent RootExpression operand list
        :param context
        """
        const_object = Constant.Neo4jConstant(constant, uuid, index, context)
        hash_exists = self.const_cache.get(const_object.HASH)

        if not hash_exists:
            success = self.CSV_serializer.serialize_object(const_object.serialize())
            if success:
                self.const_cache.update({const_object.HASH: str(const_object.UUID)})

        else:
            const_object = Constant.Neo4jConstant(constant, hash_exists,
                                                  index, context)
            self.CSV_serializer.serialize_object(const_object.serialize(), write_node=False, write_relationship=True)
