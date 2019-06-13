from neo4j import GraphDatabase
import Configuration
from .UseDefChainsImplementation import *


driver = GraphDatabase.driver(Configuration.analysis_database_uri, auth=(Configuration.analysis_database_user, Configuration.analysis_database_password),
                              max_connection_lifetime=60, max_connection_pool_size=1000,
                              connection_acquisition_timeout=30)

if __name__ == "__main__":
    CreateUseDefChains(driver)
