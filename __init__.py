"""
This module exports a binary ninja MLIL binary view of a file into a neo4j graph.
"""

from binaryninja import *
from . import binja_extraction
from . import UUID_Generator
from . import database


def main(bv):
    driver = database.init_db()
    uuid_obj = UUID_Generator.UUID(driver)

    binja_graph = binja_extraction.BinjaGraph(driver, uuid_obj, bv)

    binja_graph.bv_extract()


#    for func in bv:
#        func_obj = func_create()
#        for bb in func.mlil:


PluginCommand.register("Binja4j", "Export a BinaryView to Neo4j", main)
