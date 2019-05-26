from neo4j import GraphDatabase
import Configuration
from .UseDefChainsImplementation import *


driver = GraphDatabase.driver(Configuration.uri, auth=(Configuration.user, Configuration.password),
                              max_connection_lifetime=60, max_connection_pool_size=1000,
                              connection_acquisition_timeout=30)

if __name__ == "__main__":
    CreateUseDefChains(driver)
