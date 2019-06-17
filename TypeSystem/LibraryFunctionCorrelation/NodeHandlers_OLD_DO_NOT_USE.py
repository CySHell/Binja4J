# A module to define the traversal of a type definition on the graph, and to feed the definition to binary ninja

from neo4j import GraphDatabase, exceptions
import Configuration
from Common import GraphNodeInformation
from . import CorrelateLibraryFunctionInfo

########################################################################################################################

# Neo4j driver to the graph holding the type data

driver = GraphDatabase.driver(Configuration.analysis_database_uri,
                              auth=(Configuration.analysis_database_user, Configuration.analysis_database_password),
                              max_connection_lifetime=60, max_connection_pool_size=1000,
                              connection_acquisition_timeout=30)


########################################################################################################################

class TypeDefinitionTree:

    # This is the main cache used in the class, containing a mapping of a node ID to a string describing
    # its full recursive type definition in c language (meaning the string also contains definition for any
    # sub types used to define the type).
    # The key is the is the ID in the graph of the node, and the value is a list where the first element is a set
    # where the first element is the string describing the current node's definition and the second element is the
    # name of the type.
    # the rest of the elements is a list of ID's that are populated in the cache and contain the rest of the string
    # that describes the type.
    # The list containing the ID's is ordered so that the nodes with the more basic definitions appear first (so we
    # don't accidentally get type definitions with sub types that weren't defined yet).
    # {Queried_Type_Node_ID: [(Type_Definition_String, Type_Name), [Sub_Type_Def_1, ..., Sub_Type_Def_n]]}
    type_definition_cache = dict()

    def __init__(self, type_name: str, driver):
        self.type_name = type_name
        self.driver = driver
        self.node_label_map = GraphNodeInformation.get_node_label_map(self.driver)

        with self.driver.session() as session:
            result = session.run("MATCH (type {TypeName: '" + str(type_name) + "'}) "
                                 "WHERE labels(type)[0] ENDS_WITH '_DECL' "
                                 "RETURN type.Hash as type_hash, labels(type)[0] as label"
                                 )

        self.type_node_label = result.peek()['label'] + '_handler'
        self.type_node_hash = result.peek()['type_hash']

    def get_type_definition(self, current_node_label=None, current_node_hash=None):
        """
        :return: True if managed to get full definition, False otherwise
        """

        if not current_node_hash:
            current_node_hash = self.type_node_hash
        if not current_node_label:
            current_node_label = self.type_node_label

        # Run the function handler corresponding to the node label we are currently examining
        if getattr(self, current_node_label + '_handler', lambda: False)(current_node_label, current_node_hash):
            return self.type_definition_cache
        else:
            return False

    def BaseType_handler(self, current_node_label, current_node_hash):

        if current_node_hash in self.type_definition_cache:
            return True

        with self.driver.session() as session:
            result = session.run("MATCH (type:" + current_node_label + " {Hash: {current_node_hash}) "
                                 "RETURN type.TypeName as type_name, type.TypeDefinition as type_definition ",
                                 current_node_hash=current_node_hash)

            for record in result:
                self.type_definition_cache[current_node_hash] = [(record['type_definition'], record['type_name']), []]

        return True

    def CONSTANTARRAY_handler(self, current_node_label, current_node_hash):

        if current_node_hash in self.type_definition_cache:
            return True

        with driver.session() as session:
            result = session.run("MATCH (decl {HASH: '" + str(node_hash) + "'})-[]->(sub_type_node) "
                                 "RETURN sub_type_node.HASH as child_node_hash, "
                                 "       LABELS(sub_type_node)[0] as child_node_label "
                                 )

            result = session.run("MATCH (type:" + current_node_label + " {Hash: {current_node_hash})-[]->(sub_type) "
                                 "RETURN type.TypeName as type_name, type.TypeDefinition as type_definition ",
                                 current_node_hash=current_node_hash)

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
                type_definition_cache[node_hash] = [(record['type_definition'], record['type_name']),
                                                    children_node_hash_list]

            # TODO: handle a problem with adding the leaf node to the cache and return False
            return type_definition_cache

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
                type_definition_cache[node_hash] = [(record['type_definition'], record['type_name']),
                                                    function_arguments_list]

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
                type_definition_cache[node_hash] = [(record['type_definition'], record['type_name']),
                                                    children_node_hash_list]

            # TODO: handle a problem with adding the leaf node to the cache and return False
            return type_definition_cache


    def do_nothing(node_hash):
        # This function is intended for cases where no actions are needed, or for when the support
        # for the label is not implemented yet.
        pass


    # SWITCH statement to help navigate the different nodes in the graph.
    # Each node handler function receives a node hash of the corresponding node type, and returns a type_definition_cache
    # dictionary or False if no definition could be constructed.

    node_handler = {
        'BaseType': leaf_type_node_handler,
        'PARM_DECL': decl_node_handler,
        'TYPEDEF_DECL': decl_node_handler,
        'STRUCT_DECL': decl_node_handler,
        'Struct_Field_DECL': decl_node_handler,
        'ENUM_DECL': decl_node_handler,
        'ENUM_CONSTANT_DECL': leaf_type_node_handler,
        'POINTER': pointer_node_handler,
        'CONSTANTARRAY': decl_node_handler,
        'FUNCTIONNOPROTO': do_nothing,
        'FUNCTION_DECL': function_decl_handler,
    }






if __name__ == '__main__':
    function_decl_handler('722b9f4ec450100a')
    print("a")
