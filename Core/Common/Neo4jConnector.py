from ... import Configuration
from neo4j import GraphDatabase


def get_driver(db_type='BinaryView'):
    if db_type == 'BinaryView':
        return GraphDatabase.driver(Configuration.analysis_database_uri,
                                    auth=(
                                    Configuration.analysis_database_user, Configuration.analysis_database_password))
    else:
        if db_type == 'Types':
            # TODO: add a separate DB for types
            return GraphDatabase.driver(Configuration.analysis_database_uri,
                                        auth=(
                                            Configuration.analysis_database_user,
                                            Configuration.analysis_database_password))
        else:
            print("Wrong db_type give to get_driver()")

