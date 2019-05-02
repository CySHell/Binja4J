from neo4j import GraphDatabase, exceptions
import os
import threading
import csv
import time
import Configuration

driver = GraphDatabase.driver(Configuration.uri, auth=(Configuration.user, Configuration.password),
                              max_connection_lifetime=60, max_connection_pool_size=1000,
                              connection_acquisition_timeout=30)


def create_constraints():
    with driver.session() as session:
        session.run("CREATE CONSTRAINT ON (bv:BinaryView) ASSERT bv.HASH IS UNIQUE;")
        session.run("CREATE CONSTRAINT ON (bv:BinaryView) ASSERT bv.UUID IS UNIQUE;")
        session.run("CREATE CONSTRAINT ON (func:Function) ASSERT func.HASH IS UNIQUE;")
        session.run("CREATE CONSTRAINT ON (func:Function) ASSERT func.UUID IS UNIQUE;")
        session.run("CREATE CONSTRAINT ON (bb:BasicBlock) ASSERT bb.HASH IS UNIQUE;")
        session.run("CREATE CONSTRAINT ON (bb:BasicBlock) ASSERT bb.UUID IS UNIQUE;")
        session.run("CREATE CONSTRAINT ON (instr:Instruction) ASSERT instr.HASH IS UNIQUE;")
        session.run("CREATE CONSTRAINT ON (instr:Instruction) ASSERT instr.UUID IS UNIQUE;")
        session.run("CREATE CONSTRAINT ON (ex:Expression) ASSERT ex.HASH IS UNIQUE;")
        session.run("CREATE CONSTRAINT ON (ex:Expression) ASSERT ex.UUID IS UNIQUE;")
        session.run("CREATE CONSTRAINT ON (var:Variable) ASSERT var.HASH IS UNIQUE;")
        session.run("CREATE CONSTRAINT ON (var:Variable) ASSERT var.UUID IS UNIQUE;")
        session.run("CREATE CONSTRAINT ON (const:Constant) ASSERT const.HASH IS UNIQUE;")
        session.run("CREATE CONSTRAINT ON (const:Constant) ASSERT const.UUID IS UNIQUE;")

def create_nodes(filename):
    with driver.session() as session:
        filename = '\'file:/' + filename + '\' '
        print('Now Processing: ', filename)
        session.run("USING PERIODIC COMMIT 1000 "
                    "LOAD CSV WITH HEADERS FROM " + filename + "AS row "
                    "CALL apoc.merge.node([row['LABEL']], {HASH: row['HASH']}, row) yield node "
                    "SET node.UUID = row.UUID "
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
                #time.sleep(0.1)
                batch_rows[batch_index] = []

            batch_index = (batch_index + 1) % Configuration.THREAD_COUNT

            if len(thread_list) > Configuration.THREAD_COUNT:
                for thread in thread_list:
                    thread.join()
                thread_list = []

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
                # Because of the use of dynamic labels on the start\end nodes during the MATCH, and the possibility
                # of different labels between different rows within a batch - it is necessary to inefficiently go
                # through each row and commit it as a single transaction
                for row in batch_rows:
                    session.run("MATCH (start:" + row['StartNodeLabel'] + " {UUID: $start_id}) "
                                "MATCH (end:" + row['EndNodeLabel'] + " {UUID: $end_id}) "
                                "CALL apoc.merge.relationship(start, $row_type, {START_ID: start.UUID, "
                                                             "END_ID: end.UUID, TYPE: $row_type}, $row, end) yield rel "
                                "RETURN true ",start_id=row['START_ID'], end_id=row['END_ID'], row_type=row['TYPE'],
                                row=row)

                return
            except exceptions.TransientError:
                retry += 1
                time.sleep(2)
                continue
            except exceptions.ServiceUnavailable:
                time.sleep(2)
                continue

        print("Exceeded retry count for committing relationships")


if __name__ == "__main__":
    start_time = time.time()

    create_constraints()
    # handling of node and relationship DB insertions are different because nodes are independant from each other
    # so it is safe to insert them in a fast efficient manner (using indexes).
    # Relationships are dependant on the nodes they are connected to, and their creation is subject to deadlocks
    # and other multi-threading plagues.
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
