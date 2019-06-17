# A module to define the traversal of a type definition on the graph, and to feed the definition to binary ninja

from neo4j import GraphDatabase, exceptions
import Configuration
from Common import GraphNodeInformation
from . import CorrelateLibraryFunctionInfo
from binaryninja import *

########################################################################################################################

# Neo4j driver to the graph holding the type data

driver = GraphDatabase.driver(Configuration.analysis_database_uri,
                              auth=(Configuration.analysis_database_user, Configuration.analysis_database_password),
                              max_connection_lifetime=60, max_connection_pool_size=1000,
                              connection_acquisition_timeout=30)


########################################################################################################################

class TypeDefinitionTree:
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

    def insert_type_definition_into_binaryView(self, current_node_label=None, current_node_hash=None):
        """
        :return: True if managed to insert full definition, False otherwise
        """

        if not current_node_hash:
            current_node_hash = self.type_node_hash
        if not current_node_label:
            current_node_label = self.type_node_label

        # Skip definition if its already in the binary view
        if current_node_hash in self.type_definition_cache:
            return True

        # Run the function handler corresponding to the node label we are currently examining
        if getattr(self, current_node_label + '_handler', lambda: False)(current_node_hash):
            return True
        else:
            return False

    def BaseType_handler(self, current_node_hash):

        with self.driver.session() as session:
            result = session.run("MATCH (type:BaseType {Hash: {current_node_hash}) "
                                 "RETURN type.TypeName as type_name, type.TypeDefinition as type_definition ",
                                 current_node_hash=current_node_hash)

            if result.peek():
                type_definition = result.peek()['type_definition']
                type_name = result.peek()['type_name']
            else:
                print("No such node hash in the graph: ", current_node_hash)
                return False

            # Define the user type obtained from the graph
            try:
                var_type, name = bv.parse_type_string(type_definition + " " + type_name)
                bv.define_user_type(name, var_type)
                # If the type was added successfully, mark it in the cache
                self.type_definition_cache[current_node_hash] = True
                return True
            except:
                return False

    def POINTER_handler(self, current_node_hash):

        with self.driver.session() as session:
            result = session.run("MATCH (:POINTER {Hash: {current_node_hash})-[:PointerTo]->(pointee) "
                                 "RETURN pointee.Hash as pointee_hash, labels(pointee)[0] as pointee_label ",
                                 current_node_hash=current_node_hash)

            if result.peek():
                pointee_label = result.peek()['pointee_label']
                pointee_hash = result.peek()['pointee_hash']
            else:
                print("Pointer has no target, current pointer hash: ", current_node_hash)
                return False

            if self.insert_type_definition_into_binaryView(pointee_label, pointee_hash):
                # Add pointer node to cache, no need to feed it into the binaryView
                self.type_definition_cache[current_node_hash] = True
                return True

            return False

    def ENUM_DECL_handler(self, current_node_hash):

        with self.driver.session() as session:
            result = session.run("MATCH (enum:ENUM_DECL {Hash: {current_node_hash})-[:EnumDefinition]->"
                                 "(enum_field:ENUM_CONSTANT_DECL) "
                                 "RETURN enum_field.TypeDefinition as enum_index, enum_field.TypeName as field_name",
                                 current_node_hash=current_node_hash)

            if result.peek():
                enum = types.Enumeration

                for record in result:
                    try:
                        # add member - name, value
                        enum.append(record['field_name'], record['enum_index'])
                    except:
                        print(
                            "Cannot add enum member " + record['field_name'] + 'in enum with hash ' + current_node_hash)
                        return False
            else:
                print("Pointer has no target, current pointer hash: ", current_node_hash)
                return False

            result = session.run("MATCH (enum:ENUM_DECL {Hash: {current_node_hash}) "
                                 "RETURN enum.TypeName as enum_name",
                                 current_node_hash=current_node_hash)

            try:
                bv.define_user_type(result.peek()['enum_name'], Type.enumeration_type(bv.arch, enum))
                self.type_definition_cache[current_node_hash] = True
                return True
            except:
                return False

    def STRUCT_DECL_handler(self, current_node_hash):

        with self.driver.session() as session:
            result = session.run("MATCH (struct:STRUCT_DECL {Hash: {current_node_hash})-[:FieldDef]->"
                                 "(struct_field:StructFieldDecl) "
                                 "RETURN struct_field.Hash as field_hash, "
                                 "       struct_field.TypeDefinition as type_definition,"
                                 "       struct_field.TypeName as type_name ",
                                 current_node_hash=current_node_hash)

            if result.peek():
                # Structs can be recursively defined. In order to avoid such a situation the struct is
                # immitiatly inserted into the cache instead of waiting for the full definition.
                self.type_definition_cache[current_node_hash] = True

                struct = types.Structure()

                for record in result:
                    if self.insert_type_definition_into_binaryView('StructFieldDecl', record['field_hash']):
                        self.type_definition_cache[record['field_hash']] = True
                    else:
                        print("Failed to insert definition for struct field ", record['field_hash'])
                        return False

                    try:
                        # add struct member
                        var_type, name = bv.parse_type_string(record['type_definition'] + " " + record['type_name'])
                        struct.append(var_type, str(name))
                    except:
                        return False
            else:
                print("Struct has no target, current struct hash: ", current_node_hash)
                return False

            result = session.run("MATCH (struct:STRUCT_DECL {Hash: {current_node_hash}) "
                                 "RETURN struct.TypeName as struct_name",
                                 current_node_hash=current_node_hash)

            try:
                bv.define_user_type(result.peek()['struct_name'], Type.structure_type(struct))
                return True
            except:
                return False

    def UNION_DECL_handler(self, current_node_hash):

        with self.driver.session() as session:
            result = session.run("MATCH (union:UNION_DECL {Hash: {current_node_hash})-[:FieldDef]->"
                                 "(union_field) "
                                 "RETURN union_field.Hash as field_hash, "
                                 "       labels(union_field)[0] as field_label, "
                                 "       union_field.TypeDefinition as type_definition,"
                                 "       union_field.TypeName as type_name ",
                                 current_node_hash=current_node_hash)

            if result.peek():
                # Unions can be recursively defined. In order to avoid such a situation the struct is
                # immitiatly inserted into the cache instead of waiting for the full definition.
                self.type_definition_cache[current_node_hash] = True

                struct = types.Structure()
                # set type to union
                struct.type = types.StructureType.UnionStructureType

                for record in result:
                    if self.insert_type_definition_into_binaryView(record['field_label'], record['field_hash']):
                        self.type_definition_cache[record['field_hash']] = True
                    else:
                        print("Failed to insert definition for struct field ", record['field_hash'])
                        return False

                    try:
                        # add struct member
                        var_type, name = bv.parse_type_string(record['type_definition'] + " " + record['type_name'])
                        struct.append(var_type, str(name))
                    except:
                        return False
            else:
                print("Union has no target, current Union hash: ", current_node_hash)
                return False

            result = session.run("MATCH (union:UNION_DECL {Hash: {current_node_hash}) "
                                 "RETURN union.TypeName as union_name",
                                 current_node_hash=current_node_hash)

            try:
                bv.define_user_type(result.peek()['union_name'], Type.structure_type(struct))
                return True
            except:
                return False

    def FUNCTION_DECL_handler(self, current_node_hash):

        with self.driver.session() as session:
            result = session.run("MATCH (func:FUNCTION_DECL {Hash: {current_node_hash})-[:FunctionArgument]->"
                                 "(func_param:PARM_DECL) "
                                 "RETURN func_param.Hash as param_hash, "
                                 "       func_param.TypeDefinition as type_definition,"
                                 "       func_param.TypeName as type_name ",
                                 current_node_hash=current_node_hash)

            # Parse function arguments
            if result.peek():
                function_parameter_list = list()
                for record in result:
                    # If parameter type is already defined move on to the next parameter
                    if self.type_definition_cache[record['param_hash']]:
                        continue
                    if self.insert_type_definition_into_binaryView('PARM_DECL', record['param_hash']):
                        self.type_definition_cache[record['param_hash']] = True
                    else:
                        print("Failed to insert definition for function parameter ", record['type_name'])
                        return False

                    try:
                        # Define the Function parameter binaryNinja object
                        function_parameter_list.append(types.FunctionParameter(record['type_definition'],
                                                                               record['type_name']))
                    except:
                        return False
            else:
                # A function might not have any return value or arguments
                pass

            # Parse return value and function name
            result = session.run("MATCH (func:FUNCTION_DECL {Hash: {current_node_hash})-[:ReturnType]->"
                                 "(return_type) "
                                 "RETURN return_type.Hash as return_hash, "
                                 "       labels(return_type)[0] as return_label, "
                                 "       return_type.TypeDefinition as type_definition, "
                                 "       return_type.TypeName as type_name, ",
                                 current_node_hash=current_node_hash)

            return_type = None
            if result.peek():
                for record in result:
                    # If return type is already defined move on, otherwise define it
                    if not self.type_definition_cache[record['param_hash']]:
                        if self.insert_type_definition_into_binaryView(record['return_label'], record['return_hash']):
                            self.type_definition_cache[record['return_hash']] = True
                        else:
                            print("Failed to insert definition for function return value ", record['type_name'])
                            return False

                        try:
                            # Define the Function return value binaryNinja type object
                            var_type, name = bv.parse_type_string(record['type_definition'] + " " + record['type_name'])
                            bv.define_user_type(name, var_type)
                            return_type = var_type
                        except:
                            return False
            else:
                # A function might not have any return value or arguments
                pass

            # Define the function itself
            result = session.run("MATCH (func:FUNCTION_DECL {Hash: {current_node_hash}) "
                                 "RETURN func.TypeName as func_name",
                                 current_node_hash=current_node_hash)

            if result.peek():
                try:
                    func_name = result.peek()['func_name']
                    function_type = Type.function(return_type, function_parameter_list)

                    # TODO: set current_function correctly, and change its name accordingly
                    current_function.set_user_type(function_type)

                    self.type_definition_cache[current_node_hash] = True
                except:
                    print("Failed to process function :", func_name)
                    return False
`










































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
