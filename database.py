from neo4j import GraphDatabase
from . import binja_extraction

_uri = "bolt://localhost:7687"
_user = "neo4j"
_password = "user"


def init_db(uri=_uri, user=_user, password=_password):
    driver = GraphDatabase.driver(uri, auth=(user, password))

    with driver.session() as session:
        # ensure each DB contains a root object to connect all binary views to as children
        session.run("MERGE (root:Root {UUID:'0'})")
    return driver


