from neo4j import GraphDatabase, exceptions
import os
import threading
import csv
import time
import Configuration

driver = GraphDatabase.driver(Configuration.uri, auth=(Configuration.user, Configuration.password))


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
    print('Now Processing: ', filename)
    batch_rows = [[] for _ in range(Configuration.THREAD_COUNT)]
    batch_index = 0
    thread_list = []
    with open(Configuration.path + filename, 'r') as fn:
        for row in csv.DictReader(fn):
            batch_rows[batch_index].append(row)
            if len(batch_rows[batch_index]) == Configuration.BATCH_SIZE:
                thread_list.append(
                    threading.Thread(target=create_batch_relationships, args=[batch_rows[batch_index]]))
                thread_list[-1].start()
                batch_rows[batch_index] = []
            batch_index = (batch_index + 1) % Configuration.THREAD_COUNT
            if len(thread_list) > Configuration.THREAD_COUNT:
                thread_list[-1].join()

        for batch in batch_rows:
            if len(batch) > 0:
                thread_list.append(threading.Thread(target=create_batch_relationships, args=[batch]))
                thread_list[-1].start()

        for thread in thread_list:
            thread.join()


def create_batch_relationships(batch_rows):
    with driver.session() as session:
        retry = 0
        while retry < Configuration.RETRIES:
            try:
                session.run("UNWIND $row as row "
                            "WITH row as row "
                            "MATCH (start:" + batch_rows[0]['StartNodeLabel'] + " {UUID: row.START_ID}) "
                            "MATCH (end:" + batch_rows[0]['EndNodeLabel'] + " {UUID: row.END_ID}) "
                            "CALL apoc.create.relationship(start, row.TYPE,"
                            "row, end) yield rel "
                            "RETURN true", row=batch_rows)
                return True
            except exceptions.TransientError:
                retry += 1
                time.sleep(1)
                continue
        print("Exceeded retry count for committing relationships")


if __name__ == "__main__":
    start_time = time.time()

    create_constraints()
    for root, dirs, files in os.walk(Configuration.path):
        for filename in files:
            if filename.endswith('-nodes.csv'):
                create_nodes(filename)
    for root, dirs, files in os.walk(Configuration.path):
        for filename in files:
            if filename.endswith('-relationships.csv'):
                create_relationships(filename)

    end_time = time.time()
    print("Operation done in ", end_time - start_time, " seconds")
