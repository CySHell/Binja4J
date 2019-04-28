"""
This module exports a binary ninja MLIL binary view of a file into a neo4j graph.
"""

from neo4j import GraphDatabase
import time
from binaryninja import *
from . import binja_extraction
from . import UUID_Generator

def main(bv):
    start_time = time.time()

    uri = "bolt://localhost:7687"
    user = "neo4j"
    password = "user"

    driver = GraphDatabase.driver(uri, auth=(user, password))

    uuid_obj = UUID_Generator.UUID(driver)

    binja_graph = binja_extraction.BinjaGraph(driver, uuid_obj, bv)

    binja_graph.bv_extract()

    end_time = time.time()
    print("Operation done in ", end_time-start_time, " seconds")

PluginCommand.register("Binja4j", "Export a BinaryView to Neo4j", main)
