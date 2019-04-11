from neo4j import GraphDatabase
import os
import threading


uri = "bolt://localhost:7687"
user = "neo4j"
password = "user"

path = 'C:\\Users\\user\\.Neo4jDesktop\\neo4jDatabases\\database-e9d7bcc0-ef2d-413b-9bd1-a9611b47bc06\\installation-3.5.4\\\import\\'


class MergeNeo4j:

    def __init__(self):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def merge_bv(self):
        self.create_constraints()

        thread_list = []
        file_queue = []

        for root, dirs, files in os.walk(path):
            for filename in files:
                if filename.endswith('-nodes.csv'):
                    thread_list.append(threading.Thread(target=self.create_nodes(filename)))
                    thread_list[-1].start()
                else:
                    file_queue.append(filename)
        for thread in thread_list:
            thread.join()

        thread_list = []

        for filename in file_queue:
            thread_list.append(threading.Thread(target=self.create_relationships(filename)))
            thread_list[-1].start()

        for thread in thread_list:
            thread.join()

    def create_constraints(self):
        with self.driver.session() as session:

            session.run("CREATE CONSTRAINT ON (bv:BinaryView) ASSERT bv.HASH IS UNIQUE;")
            session.run("CREATE INDEX ON :BinaryView(UUID);")
            session.run("CREATE CONSTRAINT ON (func:Function) ASSERT func.HASH IS UNIQUE;")
            session.run("CREATE INDEX ON :Function(UUID);")
            session.run("CREATE CONSTRAINT ON (bb:BasicBlock) ASSERT bb.HASH IS UNIQUE;")
            session.run("CREATE INDEX ON :BasicBlock(UUID);")
            session.run("CREATE CONSTRAINT ON (instr:Instruction) ASSERT instr.HASH IS UNIQUE;")
            session.run("CREATE INDEX ON :Instruction(UUID);")
            session.run("CREATE CONSTRAINT ON (ex:Expression) ASSERT ex.HASH IS UNIQUE;")
            session.run("CREATE INDEX ON :Expression(UUID);")
            session.run("CREATE CONSTRAINT ON (var:Variable) ASSERT var.HASH IS UNIQUE;")
            session.run("CREATE INDEX ON :Variable(UUID);")

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

    def create_relationships(self, filename):

        with self.driver.session() as session:
            filename = '\'file:/' + filename + '\' '
            print('Now Processing: ', filename)
            session.run("USING PERIODIC COMMIT 1000 "
                        "LOAD CSV WITH HEADERS FROM " + filename + "AS row "
                        "UNWIND keys(row) as key "
                        "UNWIND row[key] as val "
                        "MATCH (start {UUID: row['START_ID']}), (end {UUID: row['END_ID']}) "
                        "CALL apoc.merge.relationship(start, row['TYPE'], {}, {}, end) yield rel "
                        "WITH rel as new_rel, key, val "
                        "CALL apoc.create.setRelProperty([new_rel], key, val) yield rel "
                        "RETURN rel.ID "
                        )


merge = MergeNeo4j()
merge.merge_bv()
