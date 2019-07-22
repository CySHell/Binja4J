from Core.Common import Neo4jConnector


class ExecutionPaths:
    """
    A class that contains all execution paths through a specific function
    """

    neo4j_bolt_driver = Neo4jConnector.get_driver()

    def __init__(self, binary_view_uuid, function_uuid):
        self.bv_id = binary_view_uuid
        self.func_id = function_uuid
        self.exec_paths = set()
        self.variable_info = set()
        # This dict associates a basic block with a variable that is defined or used within it.
        # It has the following structure:
        # {
        #  basic_block_uuid:
        #   {
        #    variable_name:
        #       {
        #        # indexes are always within the block
        #        'DefinedAt': set_of_instructionNode_uuid,
        #        'UsedAt': set_of_instructionNode_uuid,
        #       }
        #   }
        # }
        self.variable_use_def = dict()

    def get_execution_paths(self):
        """
        :return: A set ExecPath objects representing all the execution paths within the function
        """
        x_paths = self.get_execution_path_iterator()
        self.init_function_vars_dict()
        for path in x_paths:
            self.exec_paths.add(ExecPath(self.bv_id, self.func_id, path.self.variable_use_def).build_path())

    def get_execution_path_iterator(self):
        """
        Gets all the leaves of the control flow, meaning all basic blocks that have no outgoing control edges
        :return: path: an ordered list containing BasicBlock uuids representing a specific path.
        TODO: Deal with a case where the last instruction of the leaf is a tailcall.
        """

        with self.neo4j_bolt_driver.session() as session:
            result = session.run("MATCH (:BasicBlock)-"
                                 "[r:MemberBB|Branch {RootFunction: $rf, RootBinaryView: $rbv}]->(bb:BasicBlock) "
                                 "WHERE NOT (bb)-[:Branch {RootFunction: $rf, RootBinaryView: $rbv}]->(:BasicBlock) "
                                 "MATCH (:Function)-[:MemberBB {RootFunction: $rf, RootBinaryView: $rbv}]-"
                                 "(start:BasicBlock) "
                                 "CALL apoc.algo.allSimplePaths(start, bb, 'Branch>', 999) YIELD path "
                                 "WITH[p in collect(path) | nodes(p)] as paths "
                                 "UNWIND paths as path_nodes "
                                 "RETURN[n IN path_nodes | n.UUID] ",
                                 rf=self.func_id, rbv=self.bv_id)

            if result:
                for record in result:
                    for path in record:
                        # node is an ordered list of basic blocks comprising the execution path
                        # ['80a1b752-dcca-43aa-8c1f-6bffcbf213b6', '0404b925-dcd8-440e-b02d-7627393de6a0']
                        yield (path)
            else:
                print("Failed to receive any valid execution paths from function: ", self.func_id)

    def init_function_vars_dict(self):
        with self.neo4j_bolt_driver.session() as session:
            result = session.run(
                "MATCH (v:Variable)-[UseDef:DefinedAt|UsedAt {RootFunction: $rf, RootBinaryView: $rbv}]"
                "->(i:Instruction) "
                "WITH v,UseDef,i "
                "MATCH (:Instruction)-[rel:InstructionChain|NextInstruction]->(i) "
                "RETURN v.Name as VarName, v.SourceVarType as VarSource, rel.RootBasicBlock as BasicBlockUUID, "
                "i.UUID as InstructionUUID, type(UseDef) as RelType",
                rf=self.func_id, rbv=self.bv_id)

            if result:
                for record in result:
                    if not self.variable_use_def.get(record['VarName']) or                                  \
                           self.variable_use_def.get(record['VarName']).get(record['RelType']):
                        self.variable_use_def[record['BasicBlockUUID']].update(record['RelType'].update(
                            {
                                'InstructionUUID': record['InstructionUUID'],
                                'BasicBlockUUID': record['BasicBlockUUID'],
                                'VarSource': record['VarSource']
                            }
                        ))
                    else:
                        self.variable_use_def.update(
                            {
                                record['VarName']:
                                    {
                                        record['RelType']: {
                                            'InstructionUUID': record['InstructionUUID'],
                                            'BasicBlockUUID': record['BasicBlockUUID'],
                                            'VarSource': record['VarSource']
                                        }
                                    }
                            }
                        )
            else:
                print("No variables found under function: ", self.func_id)


class ExecPath:
    """
    A class that represents a single execution path through a specific function.
    This representation focuses on data-flow of variables through the path.
    Instead of following the instruction opcode themselves, This class defines the path as a UNION
    of all dataflow paths of variables within it - each variable has its own def \ use chain.
    """

    def __init__(self, binary_view_id: str, function_id: str, path: list, variable_use_def: dict):
        """
        :param binary_view_id: UUID of the binary view containing the function
        :param function_id: UUID of the function
        :param path: A set containing lists, each list contains UUID of ordered basic blocks that comprise a single
                     execution flow through the function
        """
        self.bv_id = binary_view_id
        self.func_id = function_id
        self.path = path
        self.variable_use_def = variable_use_def

    def build_path(self):
        print(self.path)
        print(self.variable_use_def)
        print("*" * 30)


if __name__ == '__main__':
    xp = ExecutionPaths('53d56392-1f20-44c6-857a-11826bae920c', '7c896728-a515-4077-9fc8-e19e12cc6e70')
    xp.get_execution_paths()
