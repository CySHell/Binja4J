from neo4j import GraphDatabase, exceptions
import os
import threading, multiprocessing
import csv

uri = "bolt://localhost:7687"
user = "neo4j"
password = "user"

path = 'C:\\Users\\user\\.Neo4jDesktop\\neo4jDatabases\\database-56ba8de5-3d81-47fc-8c2e-279758ca709a\\installation-3.5.4\\\import\\'

driver = GraphDatabase.driver(uri, auth=(user, password))


def create_constraints():
    with driver.session() as session:
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
        session.run("CREATE CONSTRAINT ON (const:Constant) ASSERT const.HASH IS UNIQUE;")
        session.run("CREATE INDEX ON :Constant(UUID);")


def create_nodes(filename):
    with driver.session() as session:
        filename = '\'file:/' + filename + '\' '
        print('Now Processing: ', filename)
        session.run("USING PERIODIC COMMIT 1000 "
                    "LOAD CSV WITH HEADERS FROM " + filename + "AS row "
                                                               "CALL apoc.merge.node([row['LABEL']], {HASH: row['HASH']}, row) yield node "
                                                               "RETURN true "
                    )


def create_relationships(filename):
    with driver.session() as session:
        #filename = '\'file:/' + filename + '\' '
        print('Now Processing: ', filename)
        #session.run("USING PERIODIC COMMIT 1000 "
        #            "LOAD CSV WITH HEADERS FROM " + filename + "AS row "
        #                                                       "MATCH (start {UUID: row['START_ID']}) "
        #                                                       "MATCH (end {UUID: row['END_ID']}) "
        #                                                       "CALL apoc.create.relationship(start, row['TYPE'], "
        #                                                       "row, end) yield rel "
        #                                                       "RETURN true"
        #            )
        batch_rows = []
        counter = 0
        thread_list = []
        with open(path + filename, 'r') as fn:
            for row in csv.DictReader(fn):
                batch_rows.append(row)
                counter += 1
                if counter == 100:
                    thread_list.append(threading.Thread(target=test_create_relationship, args=[batch_rows]))
                    thread_list[-1].start()
                    counter = 0
                    batch_rows = []
                if len(thread_list) > 16:
                    thread_list[0].join()
            if counter is not 0:
                thread_list.append(threading.Thread(target=test_create_relationship, args=[batch_rows]))
                thread_list[-1].start()
            for thread in thread_list:
                thread.join()

def test_create_relationship(batch_rows):
    with driver.session() as session:
        with session.begin_transaction() as tx:
            #for row in batch_rows:
            retry = False
            while not retry:
                try:
                    #print(batch_rows[0])
                    res = tx.run("UNWIND $rows as row "
                           "MATCH (start {UUID: row['START_ID']}) "
                           "MATCH (end {UUID: row['END_ID']}) "
                           "CALL apoc.create.relationship(start, row['TYPE'],"
                           "row, end) yield rel "
                           "RETURN row", rows=batch_rows)
                    retry = False
                    print(res.peek())
                except exceptions.TransientError:
                    retry = True


def parallel_test(filename):
    print("processing: ", filename)
    with driver.session() as session:
        filename = '\'file:/' + filename + '\' '
        first_query = "\"LOAD CSV WITH HEADERS FROM " + filename + " AS row " \
                      "MATCH (start {UUID: row['START_ID']}) " \
                      "MATCH (end {UUID: row['END_ID']}) " \
                      "RETURN start, end, row \""    \

        second_query = "\"CALL apoc.merge.relationship(start, row['TYPE'],"  \
                       "{START_ID: row['START_ID'], END_ID: row['END_ID']}, row, end) yield rel " \
                       "RETURN True\""

        session.run("CALL apoc.periodic.iterate(" + first_query + ", " + second_query + ","
                                                "{BatchSize: 100, parallel: true, iterateList: true})")


if __name__ == "__main__":
    create_constraints()
    with multiprocessing.Pool(processes=10) as pool:
        for root, dirs, files in os.walk(path):
            for filename in files:
                if filename.endswith('-nodes.csv'):
                    pool.map(create_nodes, [filename])
        for root, dirs, files in os.walk(path):
            for filename in files:
                if filename.endswith('-relationships.csv'):
                    pool.map(create_relationships, [filename])
