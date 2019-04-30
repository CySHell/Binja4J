from neo4j import GraphDatabase, exceptions
import os
import threading, multiprocessing
import csv
import time

THREAD_COUNT = 32
BATCH_SIZE = 50
RETRIES = 5

uri = "bolt://localhost:7687"
user = "neo4j"
password = "user"

path = 'C:\\Users\\user\\.Neo4jDesktop\\neo4jDatabases\\database-924d535e-f415-4824-8c6d-653b2e50f04d\\installation-3.5.4\\\import\\'

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
        # filename = '\'file:/' + filename + '\' '

        print('Now Processing: ', filename)
        batch_rows = [[] for _ in range(THREAD_COUNT)]
        batch_index = 0
        thread_list = []
        with open(path + filename, 'r') as fn:
            for row in csv.DictReader(fn):
                batch_rows[batch_index].append(row)
                if len(batch_rows[batch_index]) == BATCH_SIZE:
                    thread_list.append(
                        threading.Thread(target=test_create_relationship, args=[batch_rows[batch_index]]))
                    thread_list[-1].start()
                    batch_rows[batch_index] = []
                batch_index = (batch_index + 1) % THREAD_COUNT
                if len(thread_list) > THREAD_COUNT:
                    thread_list[-1].join()

            for batch in batch_rows:
                if len(batch) > 0:
                    thread_list.append(threading.Thread(target=test_create_relationship, args=[batch]))
                    thread_list[-1].start()

            for thread in thread_list:
                thread.join()


def test_create_relationship(batch_rows):
    with driver.session() as session:
        retry = 0
        while retry < RETRIES:
            try:
                session.run("UNWIND $row as row "
                            "WITH row as row "
                            "MATCH (start:" + batch_rows[0]['StartNodeLabel'] + " {UUID: row.START_ID}) "
                            "MATCH (end:" + batch_rows[0]['EndNodeLabel'] + " {UUID: row.END_ID}) "
                            "CALL apoc.create.relationship(start, row.TYPE,"
                            "row, end) yield rel "
                            "RETURN true", row=batch_rows)
                break
            except exceptions.TransientError:
                retry += 1
                continue


if __name__ == "__main__":
    start_time = time.time()
    create_constraints()
    with multiprocessing.Pool(processes=10) as pool:
        for root, dirs, files in os.walk(path):
            for filename in files:
                if filename.endswith('-nodes.csv'):
                    #pool.map(create_nodes, [filename])
                    create_nodes(filename)
        for root, dirs, files in os.walk(path):
            for filename in files:
                if filename.endswith('-relationships.csv'):
                    #pool.map(create_relationships, [filename])
                    create_relationships(filename)
    end_time = time.time()
    print("Operation done in ", end_time-start_time, " seconds")
