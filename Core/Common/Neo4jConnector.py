from ... import Configuration
from neo4j import GraphDatabase


def get_driver():
    return GraphDatabase.driver(Configuration.analysis_database_uri,
                                auth=(Configuration.analysis_database_user, Configuration.analysis_database_password))
