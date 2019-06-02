"""
This module exports a binary ninja MLIL binary view of a file into a neo4j graph.
"""

from neo4j import GraphDatabase
import time
from binaryninja import *
from .CSV_Processing import BuildCSV
from .Common import UUID_Generator
from . import Configuration


def main(bv):
    start_time = time.time()

    driver = GraphDatabase.driver(Configuration.uri, auth=(Configuration.user, Configuration.password))

    uuid_obj = UUID_Generator.UUID(driver)

    binja_graph = BuildCSV.BinjaGraph(driver, uuid_obj, bv)

    binja_graph.bv_extract()

    end_time = time.time()
    print("Operation done in ", end_time - start_time, " seconds")


PluginCommand.register("Binja4j", "Export a BinaryView to Neo4j", main)
