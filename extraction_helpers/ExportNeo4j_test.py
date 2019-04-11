from neo4j import GraphDatabase

uri = "bolt://localhost:7687"
user = "neo4j"
password = "user"

class MergeNeo4j:

    def __init__(self):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def merge_bv(self):
        self.create_constraints()
        self.create_nodes('BasicBlocks-nodes.csv')
        self.create_nodes('BinaryView-nodes.csv')
        self.create_nodes('Expressions-nodes.csv')
        self.create_nodes('Functions-nodes.csv')
        self.create_nodes('Instructions-nodes.csv')
        self.create_nodes('Vars-nodes.csv')

        #self.binary_view_to_neo4j()
        #self.function_to_neo4j()
        #self.basic_block_to_neo4j()

    def create_constraints(self):
        with self.driver.session() as session:
            session.run("CREATE CONSTRAINT ON (bv:BinaryView) ASSERT bv.HASH IS UNIQUE;")
            session.run("CREATE INDEX ON :BinaryView(UUID);")
            session.run("CREATE CONSTRAINT ON (func:Function) ASSERT func.HASH IS UNIQUE;")
            session.run("CREATE INDEX ON :Function(UUID);")
            session.run("CREATE CONSTRAINT ON (bb:BasicBlock) ASSERT bb.HASH IS UNIQUE;")
            session.run("CREATE INDEX ON :BasicBlock(UUID);")

    def create_nodes(self, filename):

        with self.driver.session() as session:
            filename = '\'file:/' + filename + '\' '
            print('Now Processing: ', filename)
            session.run("USING PERIODIC COMMIT 1000 "
                        "LOAD CSV WITH HEADERS FROM " + filename + "AS row "
                        "UNWIND keys(row) as key "
                        "UNWIND row[key] as val "
                        "CALL apoc.merge.node([row['LABEL']], {HASH: row['HASH']}, {}) yield node "
                        "WITH node as new_node, key, val "
                        "CALL apoc.create.setProperty([new_node], key, val) yield node "
                        "RETURN node.UUID "
                        )

    def binary_view_to_neo4j(self):
        with self.driver.session() as session:
            session.run("CREATE CONSTRAINT ON (bv:BinaryView) ASSERT bv.HASH IS UNIQUE;")
            session.run("CREATE INDEX ON :BinaryView(UUID);")


            session.run("LOAD CSV WITH HEADERS FROM 'file:/BinaryView-nodes.csv' AS bv_row "
                        "UNWIND keys(bv_row) as key "
                        "UNWIND bv_row[key] as val "
                        "CALL apoc.merge.node([bv_row['LABEL']], {HASH: bv_row['HASH']}, {}) yield node "
                        "WITH node as new_node, key, val "
                        "CALL apoc.create.setProperty([new_node], key, val) yield node "
                        "RETURN node.UUID "
                        )

    def function_to_neo4j(self):
        with self.driver.session() as session:
            session.run("CREATE CONSTRAINT ON (func:Function) ASSERT func.HASH IS UNIQUE;")
            session.run("CREATE INDEX ON :Function(UUID);")

            session.run("USING PERIODIC COMMIT "
                        "LOAD CSV WITH HEADERS FROM 'file:///Functions-nodes.csv' AS Functions "
                        "MERGE (func:Function {HASH: toInteger(Functions.HASH)})"
                        "SET func.UUID = toInteger(Functions.UUID)"
                        )
            session.run("LOAD CSV WITH HEADERS FROM 'file:///MemberFunc-relationships.csv' AS MemberFunc_rel "
                        "MATCH (parent:BinaryView {UUID: toInteger(MemberFunc_rel.START_ID)})"
                        "MATCH (child:Function {UUID: toInteger(MemberFunc_rel.END_ID)})"
                        "MERGE (parent)-[rel: MemberFunc]->(child)"
                        "SET rel.offset = toInteger(MemberFunc_rel.Offset)"
                        )

    def basic_block_to_neo4j(self):
        with self.driver.session() as session:
            session.run("CREATE CONSTRAINT ON (bb:BasicBlock) ASSERT bb.HASH IS UNIQUE;")
            session.run("CREATE INDEX ON :BasicBlock(UUID);")

            session.run("USING PERIODIC COMMIT "
                        "LOAD CSV WITH HEADERS FROM 'file:///BasicBlocks-nodes.csv' AS basic_block_line "
                        "MERGE (bb:BasicBlock {HASH: toInteger(basic_block_line.HASH)})"
                        "SET bb.UUID = toInteger(basic_block_line.UUID)"
                        )
            session.run("LOAD CSV WITH HEADERS FROM 'file:///Branch-relationships.csv' AS branch_rel_line "
                        "MATCH (parent:BasicBlock {UUID: toInteger(branch_rel_line.START_ID)})"
                        "MATCH (child:BasicBlock {UUID: toInteger(branch_rel_line.END_ID)})"
                        "MERGE (parent)-[rel:Branch]->(child)"
                        "SET rel.bb_offset = toInteger(branch_rel_line.bb_offset), "
                        "    rel.branch_condition = toInteger(branch_rel_line.BranchCondition)"
                        )

            session.run("LOAD CSV WITH HEADERS FROM 'file:///Branch-relationships.csv' AS branch_rel_line "
                        "WITH toInteger(branch_rel_line.START_ID) as start, toInteger(branch_rel_line.END_ID) as end,"
                        "     toInteger(branch_rel_line.ParentFunction) as parent_func "
                        "MATCH (:BasicBlock {UUID: start})-[rel1:Branch]-(:BasicBlock {UUID: end}) "
                        "MATCH (pfunc: Function {UUID: parent_func}) "
                        "CALL apoc.create.setRelProperty([rel1], 'parent_func_hash', pfunc.HASH) yield rel "
                        "RETURN rel"
                        )

            session.run("LOAD CSV WITH HEADERS FROM 'file:///MemberBB-relationships.csv' AS MemberBB_rel "
                        "MATCH (parent:Function {UUID: toInteger(MemberBB_rel.START_ID)})"
                        "MATCH (child:BasicBlock {UUID: toInteger(MemberBB_rel.END_ID)})"
                        "MERGE (parent)-[rel:MemberBB]->(child)"
                        "SET rel.bb_offset = toInteger(MemberBB_rel.bb_offset), "
                        "    rel.branch_condition = toInteger(MemberBB_rel.BranchCondition)"
                        )

    def extract_attributes(self, attr_dict):
        return list(attr_dict)

merge = MergeNeo4j()
merge.merge_bv()
