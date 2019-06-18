"""
This module exports a binary ninja MLIL binary view of a file into a neo4j graph.
"""

from neo4j import GraphDatabase
import time
from binaryninja import *
from .CSV_Processing import BuildCSV
from .Common import UUID_Generator
from . import Configuration
from .TypeSystem.LibraryFunctionCorrelation import NodeHandlers


def export_bv(bv):
    start_time = time.time()

    driver = GraphDatabase.driver(Configuration.analysis_database_uri, auth=(Configuration.analysis_database_user, Configuration.analysis_database_password))

    uuid_obj = UUID_Generator.UUID(driver)

    binja_graph = BuildCSV.BinjaGraph(driver, uuid_obj, bv)

    binja_graph.bv_extract()

    end_time = time.time()
    print("Operation done in ", end_time - start_time, " seconds")

def annotate_functions(bv):

    start_time = time.time()

    driver = GraphDatabase.driver(Configuration.analysis_database_uri, auth=(Configuration.analysis_database_user, Configuration.analysis_database_password))

    for func in bv.functions:
        if not func.name.startswith('sub_'):
            type_def_tree = NodeHandlers.TypeDefinitionTree(func.name, driver, bv)
            type_def_tree.insert_type_definition_into_binaryView()

    end_time = time.time()
    print("Operation done in ", end_time - start_time, " seconds")

PluginCommand.register("Binja4j", "Export a BinaryView to Neo4j", export_bv)
PluginCommand.register("Type_Anotate", "Defines a type according to pre-parsed header files", annotate_functions)
