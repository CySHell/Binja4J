from neo4j import GraphDatabase, exceptions
import os
import threading
import csv
import time
import Configuration
import xxhash

driver = GraphDatabase.driver(Configuration.analysis_database_uri,
                              auth=(Configuration.analysis_database_user, Configuration.analysis_database_password),
                              max_connection_lifetime=60, max_connection_pool_size=1000,
                              connection_acquisition_timeout=30)


def create_constraints():
    with driver.session() as session:
        session.run("CREATE CONSTRAINT ON (bv:BinaryView) ASSERT bv.HASH IS UNIQUE;")
        session.run("CREATE CONSTRAINT ON (func:Function) ASSERT func.HASH IS UNIQUE;")
        session.run("CREATE CONSTRAINT ON (bb:BasicBlock) ASSERT bb.HASH IS UNIQUE;")
        session.run("CREATE CONSTRAINT ON (instr:Instruction) ASSERT instr.HASH IS UNIQUE;")
        session.run("CREATE CONSTRAINT ON (ex:Expression) ASSERT ex.HASH IS UNIQUE;")
        session.run("CREATE CONSTRAINT ON (var:Variable) ASSERT var.HASH IS UNIQUE;")
        session.run("CREATE CONSTRAINT ON (const:Constant) ASSERT const.HASH IS UNIQUE;")
        session.run("CREATE CONSTRAINT ON (string:String) ASSERT string.HASH IS UNIQUE;")
        session.run("CREATE CONSTRAINT ON (progsym:Symbol) ASSERT progsym.HASH IS UNIQUE;")


def create_nodes(filename):
    with driver.session() as session:
        filename = '\'file:/' + filename + '\' '
        print('Now Processing: ', filename)
        session.run("USING PERIODIC COMMIT 1000 "
                    "LOAD CSV WITH HEADERS FROM " + filename + "AS row "
                                                               "CALL apoc.merge.node([row['LABEL']], {HASH: row['HASH']}, row) yield node "
                                                               "RETURN true "
                    )
        session.close()

def create_relationships(filename):
    print('Now Processing: ', filename)
    batch_rows = [list() for _ in range(Configuration.THREAD_COUNT)]
    batch_index = 0
    thread_list = list()
    with open(Configuration.analysis_database_path + filename, 'r') as fn:
        for row in csv.DictReader(fn):
            batch_rows[batch_index].append(row)

            if len(batch_rows[batch_index]) == Configuration.BATCH_SIZE:
                thread_list.append(
                    threading.Thread(target=create_batch_relationships, args=[batch_rows[batch_index]]))
                thread_list[-1].start()
                batch_rows[batch_index] = list()

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


def test_create_relationships(filename):
    with driver.session() as session:
        with open(Configuration.analysis_database_path + filename, 'r') as fn:
            sample_row = next(csv.DictReader(fn))

        filename = '\"file:/' + filename + '\" '
        print('Now Processing: ', filename)

        if sample_row:
            cypher_query = "call apoc.periodic.iterate("
            cypher_query += "'CALL apoc.load.csv(" + filename + ", {header: true}) yield map as row ' , "
            cypher_query += "'CALL apoc.search.nodeAll({" + sample_row['StartNodeLabel'] + ": \"HASH\"}, \"exact\", " \
                                                                                  "row.START_ID) yield node as start "
            cypher_query += "CALL apoc.search.nodeAll({" + sample_row['EndNodeLabel'] + ": \"HASH\"}, \"exact\", " \
                                                                                  "row.END_ID) yield node as end "
            cypher_query += "CALL apoc.merge.relationship(start, row.TYPE, {ContextHash: row.ContextHash}, row, end) " \
                            "yield rel " \
                            "RETURN true ', " \
                            "{concurrency: 200, batchSize: 5, iterateList:true, retries: 1000, parallel:true})"
            result = session.run(cypher_query)
            for record in result:
                print(record)
                print("*" * 30)

        else:
            print("Failed to load csv file: ", filename)


def create_batch_relationships(batch_rows):
    with driver.session() as session:
        retry = 0
        while retry < Configuration.RETRIES:
            try:
                # Because of the use of dynamic labels on the start\end nodes during the MATCH, and the possibility
                # of different labels between different rows within a batch - it is necessary to inefficiently go
                # through each row and commit it as a single transaction
                # TODO: figure out how to do this more efficiently
                for row in batch_rows:
                    session.run("MATCH (start:" + row['StartNodeLabel'] + " {HASH: $start_id}) "
                                                                          "MATCH (end:" + row[
                                    'EndNodeLabel'] + " {HASH: $end_id}) "
                                                      "CALL apoc.merge.relationship(start, $row_type,"
                                                      " {ContextHash: $context_hash}, $row, end) yield rel "
                                                      "RETURN true ", start_id=row['START_ID'], end_id=row['END_ID'],
                                row_type=row['TYPE'], context_hash=row['ContextHash'], row=row)

                return
            except exceptions.TransientError:
                retry += 1
                time.sleep(2)
                continue
            except exceptions.ServiceUnavailable:
                time.sleep(2)
                continue
            except TypeError as e:
                print("TypeError: ", e)
        print("Exceeded retry count for committing relationships")
        session.sync()


def BinaryViewExists():
    with driver.session() as session:
        fname = '\'file:/BinaryView-nodes.csv\''
        return session.run("LOAD CSV WITH HEADERS FROM " + fname + "AS row "
                                                                   "MATCH (bv:BinaryView {HASH: row.HASH}) "
                                                                   "RETURN exists(bv.HASH) "
                           ).peek()


def GraphCleanup():
    # Clean up all the helper attributes from the graph
    node_attributes_to_clean = ['LABEL', 'RootFunction', 'RootBasicBlock', 'RootInstruction', 'RootExpression']
    relationship_attributes_to_clean = ['START_ID', 'END_ID', 'TYPE', 'StartNodeLabel', 'EndNodeLabel']

    fname = '\'file:/BinaryView-nodes.csv\''
    node_cypher_expression = ''
    relationship_cypher_expression = ''

    for attribute in node_attributes_to_clean:
        node_cypher_expression += 'REMOVE n.' + attribute + ' '
    for attribute in relationship_attributes_to_clean:
        relationship_cypher_expression += 'REMOVE rel.' + attribute + ' '

    cypher_expression = node_cypher_expression + relationship_cypher_expression

    with driver.session() as session:
        session.run("LOAD CSV WITH HEADERS FROM " + fname + "AS row "
                                                            "MATCH (n)-[rel {RootBinaryView: row.HASH}]->() "
                    + cypher_expression)
        session.sync()


if __name__ == "__main__":
    start_time = time.time()

    create_constraints()
    # handling of node and relationship DB insertions are different because nodes are independent from each other
    # so it is safe to insert them in a fast efficient manner (using indexes).
    # Relationships are dependant on the nodes they are connected to, and their creation is subject to deadlocks
    # and other multi-threading plagues.

    if not BinaryViewExists():
        for root, dirs, files in os.walk(Configuration.analysis_database_path):
            for filename in files:
                if filename.endswith('-nodes.csv'):
                    create_nodes(filename)
        for root, dirs, files in os.walk(Configuration.analysis_database_path):
            for filename in files:
                if filename.endswith('-relationships.csv'):
                    test_create_relationships(filename)
    else:
        print("BinaryView already exists in DB, skipping export.")

    print("Starting graph node attribute cleanup...")
    GraphCleanup()

    end_time = time.time()
    print("Operation done in ", end_time - start_time, " seconds")
