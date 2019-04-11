"""
this module contains all the procedures for extracting data from a binary ninja binary view.
"""

from .extraction_helpers import BinaryView, Function, BasicBlock, \
    Instruction, Var, Expression

from . import CSV_Helper


class BinjaGraph:

    def __init__(self, driver, uuid_obj, bv):
        self._driver = driver
        self._uuid_obj = uuid_obj
        self.bv = bv
        self.CSV_serializer = CSV_Helper.CSV_Serialize()
        # {HASH: UUID}
        self.basic_block_cache = dict()
        self.instruction_cache = dict()
        self.expression_cache = dict()

    def bv_extract(self):
        """
        populate the graph with relevant info from the bv itself
        :return: success: (BOOLEAN)
        """
        bv_object = BinaryView.Neo4jBinaryView(self.bv, self._uuid_obj.get_uuid())
        success = self.CSV_serializer.serialize_object(bv_object.serialize())
        if success:
            for func in self.bv:
                self.func_extract(func, bv_object.UUID)

        self.CSV_serializer.close_file_handles()

    def func_extract(self, func, bv_uuid):
        func_object = Function.Neo4jFunction(func.mlil, self._uuid_obj.get_uuid(), 'MemberFunc', bv_uuid)
        success = self.CSV_serializer.serialize_object(func_object.serialize())

        bb_control_flow_graph = [(func.mlil.basic_blocks[0], func_object.UUID, func_object.UUID, 0)]

        if success:
            current_bb = bb_control_flow_graph.pop()
            while current_bb:
                bb_control_flow_graph.extend(self.bb_extract(current_bb[0], current_bb[1], current_bb[2],
                                             current_bb[3]))
                if bb_control_flow_graph:
                    current_bb = bb_control_flow_graph.pop()
                else:
                    current_bb = False

                print(current_bb)

    def bb_extract(self, basic_block, parent_func_uuid, parent_bb_uuid, branch_condition):
        bb_object = BasicBlock.Neo4jBasicBlock(basic_block, self._uuid_obj.get_uuid(),
                                               parent_func_uuid, parent_bb_uuid, branch_condition)

        # caching mechanism, don't store the same BB twice under different UUID.
        # only update relationships
        hash_exists = self.basic_block_cache.get(str(bb_object.HASH))
        if not hash_exists:
            success = self.CSV_serializer.serialize_object(bb_object.serialize())
            if success:
                self.basic_block_cache.update({str(bb_object.HASH): bb_object.UUID})
                # build the instruction chain under the BB
                parent_bb_uuid = bb_object.UUID
                parent_instruction_uuid = bb_object.UUID
                for instruction in basic_block:
                    parent_instruction_uuid = self.instruction_extract(instruction, parent_bb_uuid,
                                                                       parent_instruction_uuid)
        else:
            bb_object = BasicBlock.Neo4jBasicBlock(basic_block, hash_exists,
                                                   parent_func_uuid, parent_bb_uuid, branch_condition)
            success = self.CSV_serializer.serialize_object(bb_object.serialize())

        outgoing_edges_list = []

        for branch in basic_block.outgoing_edges:
            if not branch.back_edge:
                outgoing_edges_list.append([branch.target, parent_func_uuid, bb_object.UUID, branch.type.value])

        return outgoing_edges_list

    def instruction_extract(self, instruction, parent_bb_uuid, parent_instruction_uuid, operand_index=0,
                            relationship_label=None):
        """

        :param relationship_label:
        :param instruction:
        :param parent_uuid:
        :param top_level_instruction: (Bool) True if this is a top level instruction, False if this is part of an
                                             expression describing a top level instruction
        :return:
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
                self.expression_extract(instruction, instr_object.UUID, 0)
        else:
            instr_object = Instruction.Neo4jInstruction(instruction, hash_exists, relationship_label,
                                                        parent_bb_uuid, parent_instruction_uuid)
            self.CSV_serializer.serialize_object(instr_object.serialize())

        return instr_object.UUID

    def expression_extract(self, instruction, parent_instruction_uuid, operand_index):
        expr_object = Expression.Neo4jExpression(instruction.operands, self._uuid_obj.get_uuid(),
                                                 parent_instruction_uuid,
                                                 instruction.operation.name,
                                                 str(instruction.ILOperations[instruction.operation]),
                                                 operand_index)

        hash_exists = self.expression_cache.get(expr_object.HASH)

        if not hash_exists:
            success = self.CSV_serializer.serialize_object(expr_object.serialize())
            if success:
                self.expression_cache.update({expr_object.HASH: expr_object.UUID})

                index = 0
                for op_description in instruction.ILOperations[instruction.operation]:
                    op_description_type = op_description[1]

                    if op_description_type == 'expr':
                        self.expression_extract(instruction.operands[index], expr_object.UUID,
                                                index)
                        index += 1
                        continue
                    if op_description_type == 'var':
                        var_object = Var.Neo4jVar(instruction.operands[index], self._uuid_obj.get_uuid(),
                                                  index, expr_object.UUID)
                        self.CSV_serializer.serialize_object(var_object.serialize())
                        index += 1
                        continue
                    if op_description_type == 'expr_list':
                        for il_instruction in instruction.operands[index]:
                            self.expression_extract(il_instruction, expr_object.UUID,
                                                    index)
                        index += 1
                        continue
                    if op_description_type == 'var_list':
                        for il_variable in instruction.operands[index]:
                            var_object = Var.Neo4jVar(il_variable, self._uuid_obj.get_uuid(), index, expr_object.UUID)
                            self.CSV_serializer.serialize_object(var_object.serialize())
                        index += 1
                        continue
                    if op_description_type == 'int':
                        index += 1
                        continue
                    if op_description_type == 'int_list':
                        index += 1
                        continue
                    if op_description_type == 'float':
                        index += 1
                        continue
                    if op_description_type == 'var_ssa':
                        index += 1
                        continue
                    if op_description_type == 'var_ssa_dest_and_src':
                        index += 1
                        continue
                    if op_description_type == 'var_ssa_list':
                        index += 1
                        continue
                    if op_description_type == 'intrinsic':
                        index += 1
                        continue
                    index += 1
            else:
                expr_object = Expression.Neo4jExpression(instruction.operands, hash_exists,
                                                         parent_instruction_uuid,
                                                         instruction.operation.name,
                                                         str(instruction.ILOperations[instruction.operation]),
                                                         operand_index)
                success = self.CSV_serializer.serialize_object(expr_object.serialize())

            return success
