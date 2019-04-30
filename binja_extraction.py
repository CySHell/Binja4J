"""
this module contains all the procedures for extracting data from a binary ninja binary view.
"""

from .extraction_helpers import BinaryView, Function, BasicBlock, \
    Instruction, Var, Expression, Constant

from . import CSV_Helper


class BinjaGraph:
    #   The BinjaGraph object holds the main functionality of the whole plugin:
    #   1. Traverse the BinaryView and map all the objects to several CSV files
    #   2. Determine the relationships between all objects in the BinaryView
    #   3. Collect any additional information requested by the user from each object (via the /extraction_helpers)

    def __init__(self, driver, uuid_obj, bv):
        """
        :param driver: The Neo4jBoltDriver object, facilitates communication with the DB
        :param uuid_obj: Provides UUID's for newly created objects
        :param bv: BinaryNinja BinaryView object, all information is extracted from this object
        """
        self._driver = driver
        self._uuid_obj = uuid_obj
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
        bv_object = BinaryView.Neo4jBinaryView(self.bv, self._uuid_obj.get_uuid())

        # Write the dictionary into the CSV file
        success = self.CSV_serializer.serialize_object(bv_object.serialize())
        if success:
            # Iterate all functions in the BinaryView
            for func in self.bv:
                self.func_extract(func, bv_object.UUID)

        self.CSV_serializer.close_file_handles()

    def func_extract(self, func, bv_uuid: str):
        """
        :param func: BinaryNinja function object to parse
        :param bv_uuid: UUID of the containing BinaryView
        """

        func_object = Function.Neo4jFunction(func.mlil, self._uuid_obj.get_uuid(), 'MemberFunc', bv_uuid)

        hash_exists = self.function_cache.get(str(func_object.HASH))
        if not hash_exists:
            # The function doesn't already exist in the CSV
            success = self.CSV_serializer.serialize_object(func_object.serialize())
            bb_control_flow_graph = [(func.mlil.basic_blocks[0], func_object.UUID, func_object.UUID, 0)]
            processed_bb_list = []
            if success:
                # Iterate over all basic blocks in the function and create the relationships
                # between them according to the control flow graph (I.E with branches between basic blocks)
                current_bb = bb_control_flow_graph.pop()
                while current_bb:
                    bb_list, _ = self.bb_extract(current_bb[0], current_bb[1], current_bb[2],
                                                 current_bb[3])
                    bb_recursion_halt = False
                    for bb in bb_list:
                        if bb in processed_bb_list:
                            bb_recursion_halt = True

                    if not bb_recursion_halt:
                        bb_control_flow_graph.extend(bb_list)
                        processed_bb_list.extend(bb_list)
                    if bb_control_flow_graph:
                        current_bb = bb_control_flow_graph.pop()

                    else:
                        current_bb = False
        else:
            # Function object already exists in the CSV, only create the relationship (not the node itself)
            # and connect it with the existing node
            func_object = Function.Neo4jFunction(func.mlil, hash_exists, 'MemberFunc', bv_uuid)
            self.CSV_serializer.serialize_object(func_object.serialize(), write_node=False)

    def bb_extract(self, basic_block, parent_func_uuid: str, parent_bb_uuid: str, branch_condition: bool):
        """
        :param basic_block: BinaryNinja basic block object to parse
        :param parent_func_uuid: UUID of the parent function for this basic block
        :param parent_bb_uuid: UUID of the basic block that branched out to the current basic block
        :param branch_condition: branch condition to get to this basic block (0 = Unconditional, 1 = False, 2 = True)
        :return: outgoing_edges_list: (LIST) a list of all the branches from this basic block that still need parsing
        """
        bb_object = BasicBlock.Neo4jBasicBlock(basic_block, self._uuid_obj.get_uuid(),
                                               parent_func_uuid, parent_bb_uuid, branch_condition)

        hash_exists = self.basic_block_cache.get(str(bb_object.NODE_HASH))

        if not hash_exists:
            success = self.CSV_serializer.serialize_object(bb_object.serialize())
            if success:
                self.basic_block_cache.update({str(bb_object.NODE_HASH): bb_object.UUID})
                self.branch_rel_cache.update({str(bb_object.RELATIONSHIP_HASH): True})

                # build the instruction chain under the BB
                parent_bb_uuid = bb_object.UUID
                parent_instruction_uuid = bb_object.UUID
                for instruction in basic_block:
                    parent_instruction_uuid = self.instruction_extract(instruction, parent_bb_uuid,
                                                                       parent_instruction_uuid)
        else:
            bb_object = BasicBlock.Neo4jBasicBlock(basic_block, hash_exists,
                                                   parent_func_uuid, parent_bb_uuid, branch_condition)

            relationship_exists = self.branch_rel_cache.get(bb_object.RELATIONSHIP_HASH)

            if not relationship_exists:
                self.CSV_serializer.serialize_object(bb_object.serialize(), False, write_relationship=True)

        outgoing_edges_list = []
        # Iterate all branches of the current basic block and create them
        for branch in basic_block.outgoing_edges:
            if branch.back_edge is False:
                # if the branch isn't a back_edge just add it to the list to be processed in the future
                branch_struct = [branch.target, parent_func_uuid, bb_object.UUID, branch.type.value]
                outgoing_edges_list.append(branch_struct)
            else:
                # branch is a back_edge, so the basic_block it points to already exists.
                # just create the relationship between the two existing basic blocks, no new node additions
                target_bb_object = BasicBlock.Neo4jBasicBlock(branch.target, self._uuid_obj.get_uuid(),
                                                              parent_func_uuid, bb_object.UUID, branch.type.value)

                hash_exists = self.basic_block_cache.get(str(target_bb_object.NODE_HASH))

                if not hash_exists:
                    # In the edge case that the basic block that is being branched to doesn't yet exist,
                    # create it immediately and continue with the branches.
                    # Todo: Find a more elegant way to deal with this case
                    _, target_bb_object = self.bb_extract(branch.target, parent_func_uuid, bb_object.UUID,
                                                          branch.type.value)

                relationship_exists = self.branch_rel_cache.get(target_bb_object.RELATIONSHIP_HASH)
                if not relationship_exists:
                    self.CSV_serializer.serialize_object(target_bb_object.serialize(), False, write_relationship=True)
                    self.branch_rel_cache.update({str(target_bb_object.RELATIONSHIP_HASH): True})

        return outgoing_edges_list, bb_object

    def instruction_extract(self, instruction, parent_bb_uuid: str, parent_instruction_uuid: str,
                            relationship_label: str=None):
        """
        :param instruction: BinaryNinja MLIL Instruction object
        :param parent_bb_uuid: parent basic block UUID
        :param parent_instruction_uuid
        :param relationship_label: can be either "InstructionChain"(start of the chain) or "NextInstruction"
        :return: (int): the UUID of the newly created instruction object
        """

        if not relationship_label:
            relationship_label = 'InstructionChain' if parent_bb_uuid == parent_instruction_uuid else 'NextInstruction'

        instr_object = Instruction.Neo4jInstruction(instruction, self._uuid_obj.get_uuid(), relationship_label,
                                                    parent_bb_uuid, parent_instruction_uuid)

        hash_exists = self.instruction_cache.get(instr_object.HASH)
        if not hash_exists:
            success = self.CSV_serializer.serialize_object(instr_object.serialize())
            if success:
                self.instruction_cache.update({instr_object.HASH: instr_object.UUID})
                # Each instruction is further extracted into an expression (a bit like an AST)
                self.expression_extract(instruction, instr_object.UUID, 0, parent_node_type='Instruction')
        else:
            instr_object = Instruction.Neo4jInstruction(instruction, hash_exists, relationship_label,
                                                        parent_bb_uuid, parent_instruction_uuid)
            self.CSV_serializer.serialize_object(instr_object.serialize(), write_node=False)

        return instr_object.UUID

    def expression_extract(self, instruction, parent_instruction_uuid, operand_index, parent_node_type='Expression'):
        """
        An expression is a breakdown of an MLIL instruction into its individual operands under a single operation
        :param instruction: BinaryNinja MLIL Insutrction object
        :param parent_instruction_uuid: (INT)
        :param operand_index: (INT) index of the expression within the parent instruction or expression operand list
        :param parent_node_type: (STR) parent of an expression can be either an instruction or an expression
        """
        expr_object = Expression.Neo4jExpression(instruction.operands, self._uuid_obj.get_uuid(),
                                                 parent_instruction_uuid, parent_node_type,
                                                 instruction.operation.name,
                                                 str(instruction.ILOperations[instruction.operation]),
                                                 operand_index)

        hash_exists = self.expression_cache.get(expr_object.HASH)

        if not hash_exists:
            success = self.CSV_serializer.serialize_object(expr_object.serialize())
            if success:
                self.expression_cache.update({expr_object.HASH: expr_object.UUID})

                index = 0
                # Iterate the operand list according to the object types specified in the MLIL_Operations enum
                for op_description in instruction.ILOperations[instruction.operation]:
                    op_description_type = op_description[1]

                    if op_description_type == 'expr':
                        self.expression_extract(instruction.operands[index], expr_object.UUID,
                                                index)
                        index += 1
                        continue
                    if op_description_type == 'var':
                        self.var_extract(instruction.operands[index], self._uuid_obj.get_uuid(),
                                         index, expr_object.UUID)
                        index += 1
                        continue
                    if op_description_type == 'expr_list':
                        # TODO: support this op type - it is a list of parameters for the given expression
                        index += 1
                        continue
                    if op_description_type == 'var_list':
                        var_index = 0
                        for il_variable in instruction.operands[index]:
                            self.var_extract(il_variable, self._uuid_obj.get_uuid(), var_index, expr_object.UUID)
                            var_index += 1
                        index += 1
                        continue
                    if op_description_type == 'int':
                        self.constant_extract(instruction.operands[index], self._uuid_obj.get_uuid(),
                                              index, expr_object.UUID)
                        index += 1
                        continue
                    if op_description_type == 'int_list':
                        # TODO: implement this
                        index += 1
                        continue
                    if op_description_type == 'float':
                        self.constant_extract(instruction.operands[index], self._uuid_obj.get_uuid(),
                                              index, expr_object.UUID)
                        index += 1
                        continue
                    if op_description_type == 'var_ssa':
                        # TODO: implement this
                        index += 1
                        continue
                    if op_description_type == 'var_ssa_dest_and_src':
                        # TODO: implement this
                        index += 1
                        continue
                    if op_description_type == 'var_ssa_list':
                        # TODO: implement this
                        index += 1
                        continue
                    if op_description_type == 'intrinsic':
                        # TODO: implement this
                        index += 1
                        continue
                    print("op_description_type un-parsed:", op_description)
                    index += 1
        else:
            # Expression already exists, only create the relationship between the existing nodes
            expr_object = Expression.Neo4jExpression(instruction.operands, hash_exists,
                                                     parent_instruction_uuid, parent_node_type,
                                                     instruction.operation.name,
                                                     str(instruction.ILOperations[instruction.operation]),
                                                     operand_index)
            self.CSV_serializer.serialize_object(expr_object.serialize())

    def var_extract(self, var, uuid: str, index: int, parent_expr_uuid: str):
        """
        :param var: BinaryNinja MLIL_VAR object
        :param uuid: UUID to give this VAR object within the CSV
        :param index: operand index of this var within the parent expression operand list
        :param parent_expr_uuid:
        """

        var_object = Var.Neo4jVar(var, uuid, index, parent_expr_uuid)
        hash_exists = self.var_cache.get(var_object.HASH)

        if not hash_exists:
            success = self.CSV_serializer.serialize_object(var_object.serialize())
            if success:
                self.var_cache.update({var_object.HASH: var_object.UUID})
            else:
                print("Failed to create VAR object: ", var)
        else:
            var_object = Var.Neo4jVar(var, hash_exists,
                                      index, parent_expr_uuid)
            self.CSV_serializer.serialize_object(var_object.serialize(), write_node=False)

    def constant_extract(self, constant, uuid: str, index: int, parent_expr_uuid: str):
        """
        :param constant: A constant value (e.g "54343")
        :param uuid: UUID to assign to this constant
        :param index: index of the constant within the parent expression operand list
        :param parent_expr_uuid:
        """
        const_object = Constant.Neo4jConstant(constant, uuid, index, parent_expr_uuid)
        hash_exists = self.const_cache.get(const_object.HASH)

        if not hash_exists:
            success = self.CSV_serializer.serialize_object(const_object.serialize())
            if success:
                self.const_cache.update({const_object.HASH: const_object.UUID})

        else:
            const_object = Constant.Neo4jConstant(constant, hash_exists,
                                                  index, parent_expr_uuid)
            self.CSV_serializer.serialize_object(const_object.serialize(), write_node=False)
