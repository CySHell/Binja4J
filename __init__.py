"""
This module exports a binary ninja MLIL binary view of a file into a neo4j graph.
"""

from .Core.Common import Neo4jConnector
import time
from binaryninja import *
from .Core.CSV_Processing import BuildCSV
from .Core.Common import UUID_Generator
from .Core.TypeSystem.LibraryFunctionCorrelation import NodeHandlers


def export_bv(bv):
    start_time = time.time()

    driver = Neo4jConnector.get_driver()

    binja_graph = BuildCSV.BinjaGraph(driver, bv)

    binja_graph.bv_extract()

    end_time = time.time()
    print("Operation done in ", end_time - start_time, " seconds")


def annotate_functions(bv):
    start_time = time.time()

    for func in bv.functions:
        if not func.name.startswith('sub_'):
            type_def_tree = NodeHandlers.TypeDefinitionTree(func.name, bv)
            type_def_tree.insert_type_definition_into_binaryView()
        bv.reanalyze()

    end_time = time.time()
    print("Operation done in ", end_time - start_time, " seconds")

PluginCommand.register("Binja4j", "Export a BinaryView to Neo4j", export_bv)
PluginCommand.register("Type_Anotate", "Defines a type according to pre-parsed header files", annotate_functions)
