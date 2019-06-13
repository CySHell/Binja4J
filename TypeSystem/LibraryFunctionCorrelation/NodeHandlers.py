# A module to define the traversal of a type definition on the graph, and to feed the definition to binary ninja

from neo4j import GraphDatabase, exceptions
import Configuration
import xxhash

########################################################################################################################
# This is the main cache used in the class, containing a mapping of a node ID to a string describing
# its full recursive type definition in c language (meaning the string also contains definition for any
# sub types used to define the type).
# The key is the is the ID in the graph of the node, and the value is a list where the first element is a set where the
# first elemnt is the string describing the current node's definition and the second element is the name of the type.
# the rest of the elements is a list of ID's that are populated in the cache and contain the rest of the string that
# describes the type.
# The list containing the ID's is ordered so that the nodes with the more basic definitions apear first (so we
# dont accidently get type definitions with sub types that waren't defined yet).
# {Queried_Type_Node_ID: [(Type_Definition_String, Type_Name), [Sub_Type_Def_1, ..., Sub_Type_Def_n]]}

type_definition_cache = dict()

########################################################################################################################

# Neo4j driver to the graph holding the type data

driver = GraphDatabase.driver(Configuration.analysis_database_uri,
                              auth=(Configuration.analysis_database_user, Configuration.analysis_database_password),
                              max_connection_lifetime=60, max_connection_pool_size=1000,
                              connection_acquisition_timeout=30)


########################################################################################################################


def function_decl_handler(node_hash):
    # The graph traversal is all recursively handled from this function, with the function itself being
    # the root of the parsed type tree.
    # Node label 'FUNCTION_DECL'

    if node_hash in type_definition_cache:
        return type_definition_cache

    with driver.session() as session:
        result = session.run("MATCH (func_decl:FUNCTION_DECL {HASH: '" + str(node_hash) + "'}) "
                             "MATCH (func_decl)-[:Return_Type]->(return_type) "
                             "MATCH (func_decl)-[:Function_Argument]->(function_arg:PARM_DECL) "
                             "RETURN func_decl.type_definition as func_type_definition, "
                             "       return_type.HASH as return_type_node_hash, "
                             "       labels(return_type)[0] as return_type_label, "
                             "       function_arg.HASH as arg_node_hash, "
                             "       labels(function_arg)[0] as arg_label")

        function_arguments_list = list()

        for record in result:
            if not function_arguments_list:
                if node_handler[record['return_type_label']](record['return_type_node_hash']):
                    function_arguments_list.append(record['return_type_node_hash'])
                else:
                    print("Unable to parse function return type: ", record['return_type_node_hash'])
                    break
            if node_handler[record['arg_label']](record['arg_node_hash']):
                function_arguments_list.append(record['arg_node_hash'])
            else:
                print("Unable to parse function argument: ", record['arg_node_hash'])
                break

        # If I reached this part of the declaration then I am assured that all child types of this declaration
        # have been successfully added to the type cache.
        result = session.run("MATCH (decl:FUNCTION_DECL {HASH: '" + str(node_hash) + "'}) "
                             "RETURN decl.type_name as type_name, decl.type_definition as type_definition")

        for record in result:
            type_definition_cache[node_hash] = [(record['type_definition'], record['type_name']), function_arguments_list]

        # TODO: handle a problem with adding the leaf node to the cache and return False
        return type_definition_cache


def pointer_node_handler(node_hash):
    # Node Label: 'POINTER'

    if node_hash in type_definition_cache:
        return type_definition_cache

    with driver.session() as session:
        result = session.run("MATCH (p:POINTER {HASH: '" + str(node_hash) + "'})-[:PointerTo]->(pointee) "
                             "RETURN pointee.HASH as pointee_hash, LABELS(pointee)[0] as pointee_label ")

        for record in result:
            if node_handler[record['pointee_label']](record['pointee_hash']):
                type_definition_cache[node_hash] = [('void *', 'null'), [record['pointee_hash']]]
            else:
                print("Unable to parse pointee: ", record['pointee_hash'])
                return False
        return type_definition_cache


def leaf_type_node_handler(node_hash):
    # Node Label: 'Base_Type' or 'ENUM_CONSTANT_DECL'

    if node_hash in type_definition_cache:
        return type_definition_cache

    with driver.session() as session:
        result = session.run("MATCH (leaf {HASH: '" + str(node_hash) + "'}) "
                             "RETURN leaf.type_name as type_name, leaf.type_definition as type_definition ")

        for record in result:
            type_definition_cache[node_hash] = [(record['type_definition'], record['type_name']), []]

        # TODO: handle a problem with adding the leaf node to the cache and return False
        return type_definition_cache


def decl_node_handler(node_hash):
    # Node Label: 'PARM_DECL' or 'TYPEDEF_DECL' or 'STRUCT_DECL' or 'ENUM_DECL' or
    #             'CONSTANTARRAY' or

    if node_hash in type_definition_cache:
        return type_definition_cache

    with driver.session() as session:
        result = session.run("MATCH (decl {HASH: '" + str(node_hash) + "'})-[]->(sub_type_node) "
                             "RETURN sub_type_node.HASH as child_node_hash, "
                             "       LABELS(sub_type_node)[0] as child_node_label "
                             )

        children_node_hash_list = []

        for record in result:
            if node_handler[record['child_node_label']](record['child_node_hash']):
                children_node_hash_list.append(record['child_node_hash'])
            else:
                print("Unable to parse type: ", record['child_node_hash'])
                return False

        # If I reached this part of the declaration then I am assured that all child types of this declaration
        # have been successfully added to the type cache.
        result = session.run("MATCH (decl {HASH: '" + str(node_hash) + "'}) "
                             "RETURN decl.type_name as type_name, decl.type_definition as type_definition")

        for record in result:
            type_definition_cache[node_hash] = [(record['type_definition'], record['type_name']), children_node_hash_list]

        # TODO: handle a problem with adding the leaf node to the cache and return False
        return type_definition_cache


def do_nothing(node_hash):
    # This function is intended for cases where no actions are needed, or for when the support
    # for the label is not implemented yet.
    pass


# SWITCH statement to help function calls
# Each node handler function receives a node ID of the corresponding node type, and returns True
# if the node type given has been successfully updated in the type_definition_cache

node_handler = {
    'PARM_DECL': decl_node_handler,
    'TYPEDEF_DECL': decl_node_handler,
    'STRUCT_DECL': decl_node_handler,
    'Struct_Field_DECL': decl_node_handler,
    'ENUM_DECL': decl_node_handler,
    'Base_Type': leaf_type_node_handler,
    'ENUM_CONSTANT_DECL': leaf_type_node_handler,
    'POINTER': pointer_node_handler,
    'CONSTANTARRAY': decl_node_handler,
    'FUNCTIONNOPROTO': do_nothing,
}


def get_function_definitions(func_name: str):
    """
    :param func_name: function name to get definitions for
    :return: type_definition_cache if exists in graph, or False otherwise
    """
    with driver.session() as session:
        result = session.run("MATCH (func {type_name: '" + str(func_name) + "'}) "
                             "RETURN func.HASH as func_hash"
                             )

        for record in result:
            return function_decl_handler(record['func_hash'])

        return False


if __name__ == '__main__':
    function_decl_handler('722b9f4ec450100a')
    print("a")
