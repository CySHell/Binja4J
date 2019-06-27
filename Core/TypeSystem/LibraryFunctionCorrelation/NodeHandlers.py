# A module to define the traversal of a type definition on the graph, and to feed the definition to binary ninja

from neo4j import GraphDatabase
from ...Common import GraphNodeInformation
from binaryninja import *
from .... import Configuration

########################################################################################################################

# Neo4j driver to the graph holding the type data

driver = GraphDatabase.driver(Configuration.analysis_database_uri,
                              auth=(Configuration.analysis_database_user, Configuration.analysis_database_password),
                              max_connection_lifetime=60, max_connection_pool_size=1000,
                              connection_acquisition_timeout=30)


########################################################################################################################

class TypeDefinitionTree:
    type_definition_cache = dict()
    type_definition_cache_bv_reference = None
    driver = GraphDatabase.driver(Configuration.analysis_database_uri,
                                  auth=(Configuration.analysis_database_user,
                                        Configuration.analysis_database_password))

    def __init__(self, type_name: str, bv):
        self.type_name = type_name
        self.node_label_map = GraphNodeInformation.get_node_label_map(self.driver)
        self.bv = bv
        if not self.type_definition_cache_bv_reference == str(bv):
            # Each binary view holds its own defined types, so if we open up two different binary views
            # the types defined for one of them are not automatically transferred to the other.
            # By cleaning the cache for a new binary view we ensure that the script will re-define all necessary
            # definitions for the new bv.
            self.type_definition_cache_bv_reference = str(bv)
            self.type_definition_cache = dict()

    def insert_type_definition_into_binaryView(self, current_node_label=None, current_node_hash=None):
        """
        :return: True if managed to insert full definition, False otherwise
        """

        if not current_node_hash and not current_node_label:
            with self.driver.session() as session:
                result = session.run("MATCH (type {TypeName: '" + str(self.type_name) + "'}) "
                                                                                        "RETURN type.Hash as type_hash, labels(type)[0] as label"
                                     )
            if result.peek():
                current_node_label = result.peek()['label']
                current_node_hash = result.peek()['type_hash']
            else:
                # print("Type ", self.type_name, " not found in the DB, aborting.")
                return False

        # Skip definition if its already in the binary view
        if current_node_hash in self.type_definition_cache:
            return True

        # Run the function handler corresponding to the node label we are currently examining
        handler_function = getattr(self, current_node_label + '_handler', lambda x: False)

        if handler_function(current_node_hash):
            # print("Defined Function: ", self.type_name)
            return True
        else:
            return False

    def FUNCTION_DECL_handler(self, current_node_hash):

        with self.driver.session() as session:
            result = session.run("MATCH (func:FUNCTION_DECL {Hash: {current_node_hash}})-[:FunctionArgument]->"
                                 "(func_param:PARM_DECL) "
                                 "RETURN func_param.Hash as param_hash, "
                                 "       func_param.TypeDefinition as type_definition,"
                                 "       func_param.TypeName as type_name ",
                                 current_node_hash=current_node_hash)

            # Parse function arguments
            function_parameter_list = list()
            if result.peek():
                for record in result:
                    # If parameter type is already defined move on to the next parameter
                    if not self.type_definition_cache.get(record['param_hash']):
                        if self.insert_type_definition_into_binaryView('PARM_DECL', record['param_hash']):
                            self.type_definition_cache[record['param_hash']] = True
                        else:
                            print("Failed to insert definition for function parameter ", record['type_name'])
                            return False

                    try:
                        # Define the Function parameter binaryNinja object
                        function_parameter_list.append(
                            types.FunctionParameter(self.bv.get_type_by_name(record['type_name']),
                                                    record['type_name']))
                    except Exception as e:
                        print("FUNCTION_DECL_handler: Failed to process function parameter" + str(e))
                        return False

            # Parse return value and function name
            result = session.run("MATCH (func:FUNCTION_DECL {Hash: {current_node_hash}})-[:ReturnType]->"
                                 "(return_type) "
                                 "RETURN return_type.Hash as return_hash, "
                                 "       labels(return_type)[0] as return_label, "
                                 "       return_type.TypeDefinition as type_definition, "
                                 "       return_type.TypeName as type_name ",
                                 current_node_hash=current_node_hash)

            return_type = types.Type.void()

            if result.peek():
                for record in result:
                    # If return type is already defined move on, otherwise define it
                    if not self.type_definition_cache.get(record['return_hash']):
                        if self.insert_type_definition_into_binaryView(record['return_label'], record['return_hash']):
                            self.type_definition_cache[record['return_hash']] = True
                        else:
                            print("Failed to insert definition for function return value ", record['type_name'])
                            return False

                    try:
                        # Define the Function return value binaryNinja type object
                        if record['type_definition'] == 'PointerTo':
                            # Return type is a pointer
                            var_type, name = self.bv.parse_type_string(record['type_name'][:-1])
                            return_type = Type.pointer(self.bv.arch, var_type)
                        else:
                            var_type, name = self.bv.parse_type_string(
                                record['type_definition'] + " " + record['type_name'])
                            self.bv.define_user_type(name, var_type)
                            return_type = Type.named_type_from_type(name, self.bv.get_type_by_name(name))
                    except Exception as e:
                        print("FUNCTION_DECL_handler: Failed to process return value, " + str(e))
                        return False
            else:
                # A function might not have any return value or arguments
                pass

            # Define the function itself
            result = session.run("MATCH (func:FUNCTION_DECL {Hash: {current_node_hash}}) "
                                 "RETURN func.TypeName as func_name",
                                 current_node_hash=current_node_hash)

            if result.peek():
                func_name = result.peek()['func_name']
                try:
                    for func in self.bv.functions:
                        if func.name == func_name:
                            func_cc = func.calling_convention
                            function_type = Type.function(return_type, function_parameter_list, func_cc)
                            func.set_user_type(function_type)
                            if not self.fix_tailcall(func, function_parameter_list, return_type, func_cc):
                                return False
                    self.type_definition_cache[current_node_hash] = True
                except Exception as e:
                    print("Failed to process function :", func_name)
                    print(str(e))
                    return False

        print("Successfully defined function: ", func_name)


        return True

    def PARM_DECL_handler(self, current_node_hash):

        with self.driver.session() as session:
            result = session.run("MATCH (parm:PARM_DECL {Hash: {current_node_hash}})-[]->"
                                 "(sub_type) "
                                 "RETURN sub_type.Hash as sub_type_hash, "
                                 "       labels(sub_type)[0] as sub_type_label",
                                 current_node_hash=current_node_hash)

            if result.peek():
                for record in result:
                    if self.insert_type_definition_into_binaryView(record['sub_type_label'], record['sub_type_hash']):
                        self.type_definition_cache[record['sub_type_hash']] = True
                    else:
                        print("Failed to insert definition for parameter sub type", record['sub_type_hash'])
                        return False
            else:
                print("Function Parameter has no target, current parameter hash: ", current_node_hash)
                return False

            result = session.run("MATCH (parm:PARM_DECL {Hash: {current_node_hash}}) "
                                 "RETURN parm.TypeName as type_name, "
                                 "       parm.TypeDefinition as type_definition",
                                 current_node_hash=current_node_hash)

            if result.peek():
                try:
                    var_type, name = self.bv.parse_type_string(result.peek()['type_definition'] +
                                                               " " + result.peek()['type_name'])
                    self.bv.define_user_type(name, var_type)
                    self.type_definition_cache[current_node_hash] = True
                    return True
                except Exception as e:
                    print("Failed to define a user type for function parameter with hash ", current_node_hash)
                    print(str(e))
                    return False

    def BaseType_handler(self, current_node_hash):

        with self.driver.session() as session:
            result = session.run("MATCH (type:BaseType {Hash: {current_node_hash}}) "
                                 "RETURN type.TypeName as type_name, type.TypeDefinition as type_definition ",
                                 current_node_hash=current_node_hash)

            if result.peek():
                type_definition = result.peek()['type_definition']
                type_name = result.peek()['type_name']

                if type_definition == 'const void':
                    # Edge case, the binja c parser doesn't accept const as a storage type for void
                    type_definition = 'void'
            else:
                print("No such node hash in the graph: ", current_node_hash)
                return False

            # Define the user type obtained from the graph
            try:
                var_type, name = self.bv.parse_type_string(type_definition + " " + type_name)
                self.bv.define_user_type(name, var_type)
                # If the type was added successfully, mark it in the cache
                self.type_definition_cache[current_node_hash] = True
                return True
            except Exception as e:
                print('Failed to define the BaseType: ', type_definition + " " + type_name)
                print(str(e))
                return False

    def POINTER_handler(self, current_node_hash):

        with self.driver.session() as session:
            result = session.run("MATCH (:POINTER {Hash: {current_node_hash}})-[]->(pointee) "
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
            else:
                print("Failed to define the target of the pointer. target hash is: ", pointee_hash)
                return False

    def ENUM_DECL_handler(self, current_node_hash):

        with self.driver.session() as session:
            result = session.run("MATCH (enum:ENUM_DECL {Hash: {current_node_hash}})-[:EnumDefinition]->"
                                 "(enum_field:ENUM_CONSTANT_DECL) "
                                 "RETURN enum_field.TypeDefinition as enum_index, enum_field.TypeName as field_name",
                                 current_node_hash=current_node_hash)

            if result.peek():
                enum = types.Enumeration

                for record in result:
                    try:
                        # add member - name, value
                        enum.append(record['field_name'], record['enum_index'])
                    except Exception as e:
                        print(
                            "Cannot add enum member " + record['field_name'] + 'in enum with hash ' + current_node_hash)
                        print(str(e))
                        return False
            else:
                print("Pointer has no target, current pointer hash: ", current_node_hash)
                return False

            result = session.run("MATCH (enum:ENUM_DECL {Hash: {current_node_hash}}) "
                                 "RETURN enum.TypeName as enum_name",
                                 current_node_hash=current_node_hash)

            try:
                self.bv.define_user_type(result.peek()['enum_name'], Type.enumeration_type(self.bv.arch, enum))
                self.type_definition_cache[current_node_hash] = True
                return True
            except Exception as e:
                print("ENUM_DECL_handler: Failed to define enum. " + str(e))
                return False

    def STRUCT_DECL_handler(self, current_node_hash):

        with self.driver.session() as session:
            struct_name = session.run("MATCH (struct:STRUCT_DECL {Hash: {current_node_hash}}) "
                                      "RETURN struct.TypeName as struct_name",
                                      current_node_hash=current_node_hash).peek()['struct_name']

            result = session.run("MATCH (struct:STRUCT_DECL {Hash: {current_node_hash}})-[:FieldDef]->"
                                 "(struct_field:StructFieldDecl) "
                                 "RETURN struct_field.Hash as field_hash, "
                                 "       struct_field.TypeDefinition as type_definition,"
                                 "       struct_field.TypeName as type_name ",
                                 current_node_hash=current_node_hash)

            if result.peek():
                # Structs can be recursively defined. In order to avoid such a situation the struct is
                # immediately inserted into the cache instead of waiting for the full definition.
                self.type_definition_cache[current_node_hash] = True

                struct = types.Structure()
                self.bv.define_user_type(struct_name, Type.structure_type(types.Structure()))

                for record in result:
                    if self.insert_type_definition_into_binaryView('StructFieldDecl', record['field_hash']):
                        self.type_definition_cache[record['field_hash']] = True
                    else:
                        print("Failed to insert definition for struct field ", record['field_hash'])
                        return False

                    try:
                        # add struct member
                        var_type, name = self.bv.parse_type_string(
                            record['type_definition'] + " " + record['type_name'])
                        struct.append(var_type, str(name))
                    except Exception as e:
                        print("STRUCT_DECL_handler: Failed to add a struct member" + str(e))
                        return False
            else:
                print("Struct has no target, current struct hash: ", current_node_hash)
                return False

            try:
                self.bv.define_user_type(struct_name, Type.structure_type(struct))
                return True
            except Exception as e:
                print("STRUCT_DECL_handler: Failed to define Struct. " + str(e))
                return False

    def UNION_DECL_handler(self, current_node_hash):

        with self.driver.session() as session:
            union_name = session.run("MATCH (union:UNION_DECL {Hash: {current_node_hash}}) "
                                     "RETURN union.TypeName as union_name",
                                     current_node_hash=current_node_hash).peek()['union_name']

            result = session.run("MATCH (union:UNION_DECL {Hash: {current_node_hash}})-[:FieldDef]->"
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
                self.bv.define_user_type(union_name, Type.structure_type(types.Structure()))

                for record in result:
                    if self.insert_type_definition_into_binaryView(record['field_label'], record['field_hash']):
                        self.type_definition_cache[record['field_hash']] = True
                    else:
                        print("Failed to insert definition for struct field ", record['field_hash'])
                        return False

                    try:
                        # add struct member
                        var_type, name = self.bv.parse_type_string(
                            record['type_definition'] + " " + record['type_name'])
                        struct.append(var_type, str(name))
                    except Exception as e:
                        print(record['type_definition'] + "   " + record['type_name'])
                        print("UNION_DECL_handler: Failed to add union member. " + str(e))
                        return False
            else:
                print("Union has no target, current Union hash: ", current_node_hash)
                return False

            try:
                self.bv.define_user_type(union_name, Type.structure_type(struct))
                return True
            except Exception as e:
                print("UNION_DECL_handler: Failed to define union. " + str(e))
                return False

    def TYPEDEF_DECL_handler(self, current_node_hash):

        with self.driver.session() as session:
            result = session.run("MATCH (typedef:TYPEDEF_DECL {Hash: {current_node_hash}})-[]->"
                                 "(sub_type) "
                                 "RETURN sub_type.Hash as sub_type_hash, "
                                 "       labels(sub_type)[0] as sub_type_label",
                                 current_node_hash=current_node_hash)

            if result.peek():
                for record in result:
                    if self.insert_type_definition_into_binaryView(record['sub_type_label'], record['sub_type_hash']):
                        self.type_definition_cache[record['sub_type_hash']] = True
                    else:
                        print("Failed to insert definition for typedef sub type ", record['sub_type_hash'])
                        return False
            else:
                print("Typedef has no target, current struct hash: ", current_node_hash)
                return False

            result = session.run("MATCH (typedef:TYPEDEF_DECL {Hash: {current_node_hash}}) "
                                 "RETURN typedef.TypeName as type_name, "
                                 "       typedef.TypeDefinition as type_definition",
                                 current_node_hash=current_node_hash)

            if result.peek():
                try:
                    var_type, name = self.bv.parse_type_string(result.peek()['type_definition'] +
                                                               " " + result.peek()['type_name'])
                    self.bv.define_user_type(name, var_type)
                    self.type_definition_cache[current_node_hash] = True
                    return True
                except Exception as e:
                    print(str(e))
                    print("Failed to define a user type for typedef with hash ", current_node_hash)
                    return False

    def CONSTANTARRAY_handler(self, current_node_hash):

        with self.driver.session() as session:
            result = session.run("MATCH (array:CONSTANTARRAY {Hash: {current_node_hash}})-[]->"
                                 "(array_type) "
                                 "RETURN array_type.Hash as sub_type_hash, "
                                 "       labels(array_type)[0] as sub_type_label",
                                 current_node_hash=current_node_hash)

            if result.peek():
                for record in result:
                    if self.insert_type_definition_into_binaryView(record['sub_type_label'], record['sub_type_hash']):
                        self.type_definition_cache[record['sub_type_hash']] = True
                    else:
                        print("Failed to insert definition for array type ", record['sub_type_hash'])
                        return False
            else:
                print("Array has no target type, current Array hash: ", current_node_hash)
                return False

            self.type_definition_cache[current_node_hash] = True
            return True

    def INCOMPLETEARRAY_handler(self, current_node_hash):

        with self.driver.session() as session:
            result = session.run("MATCH (array:INCOMPLETEARRAY {Hash: {current_node_hash}})-[]->"
                                 "(array_type) "
                                 "RETURN array_type.Hash as sub_type_hash, "
                                 "       labels(array_type)[0] as sub_type_label",
                                 current_node_hash=current_node_hash)

            if result.peek():
                for record in result:
                    if self.insert_type_definition_into_binaryView(record['sub_type_label'], record['sub_type_hash']):
                        self.type_definition_cache[record['sub_type_hash']] = True
                    else:
                        print("Failed to insert definition for array type ", record['sub_type_hash'])
                        return False
            else:
                print("Array has no target type, current Array hash: ", current_node_hash)
                return False

            self.type_definition_cache[current_node_hash] = True
            return True

    def StructFieldDecl_handler(self, current_node_hash):

        with self.driver.session() as session:
            result = session.run("MATCH (field:StructFieldDecl {Hash: {current_node_hash}})-[]->"
                                 "(field_def) "
                                 "RETURN field_def.Hash as field_hash, "
                                 "       labels(field_def)[0] as field_label, "
                                 "       field_def.TypeDefinition as type_definition,"
                                 "       field_def.TypeName as type_name ",
                                 current_node_hash=current_node_hash)

            if result.peek():
                for record in result:
                    if self.insert_type_definition_into_binaryView(record['field_label'], record['field_hash']):
                        self.type_definition_cache[record['field_hash']] = True
                        return True
                    else:
                        print("Failed to insert definition for struct field ", record['field_hash'])
                        return False
            else:
                print("Failed to find struct field definition, struct hash:  ", current_node_hash)
                return False

    def VAR_DECL_handler(self, current_node_hash):

        print("Not handling definition of VAR_DECL with hash: ", current_node_hash)
        return True

    def FUNCTIONPROTO_OR_FUNCTIONNOPROTO_handler(self, current_node_hash):
        # No need to define the actual function in the binary view, since that will be taken care of
        # by this nodes' parent Typedef node
        with self.driver.session() as session:
            result = session.run("MATCH (func {Hash: {current_node_hash}})-[:FunctionArgument]->"
                                 "(func_param) "
                                 "RETURN func_param.Hash as param_hash, "
                                 "       labels(func_param)[0] as param_label, "
                                 "       func_param.TypeDefinition as type_definition,"
                                 "       func_param.TypeName as type_name ",
                                 current_node_hash=current_node_hash)

            # Parse function arguments
            if result.peek():
                for record in result:
                    # If parameter type is already defined move on to the next parameter
                    if self.type_definition_cache.get(record['param_hash']):
                        continue
                    if self.insert_type_definition_into_binaryView(record['param_label'], record['param_hash']):
                        self.type_definition_cache[record['param_hash']] = True
                    else:
                        print("Failed to insert definition for function parameter ", record['type_name'])
                        return False

            # Parse return value
            result = session.run("MATCH (func {Hash: {current_node_hash}})-[:ReturnType]->"
                                 "(return_type) "
                                 "RETURN return_type.Hash as return_hash, "
                                 "       labels(return_type)[0] as return_label, "
                                 "       return_type.TypeDefinition as type_definition, "
                                 "       return_type.TypeName as type_name ",
                                 current_node_hash=current_node_hash)

            if result.peek():
                for record in result:
                    # If return type is already defined move on, otherwise define it
                    if not self.type_definition_cache.get(record['return_hash']):
                        if self.insert_type_definition_into_binaryView(record['return_label'],
                                                                       record['return_hash']):
                            self.type_definition_cache[record['return_hash']] = True
                        else:
                            print("Failed to insert definition for function return value ", record['type_name'])
                            return False
        return True

    def FUNCTIONPROTO_handler(self, current_node_hash):

        if self.FUNCTIONPROTO_OR_FUNCTIONNOPROTO_handler(current_node_hash):
            return True
        else:
            return False

    def FUNCTIONNOPROTO_handler(self, current_node_hash):

        if self.FUNCTIONPROTO_OR_FUNCTIONNOPROTO_handler(current_node_hash):
            return True
        else:
            return False

    def fix_tailcall(self, func, function_parameter_list, return_type, func_cc):
        # PE's sometimes use a tailcall that jumps to the IAT\GOT entry of the function.
        # This function will label the tailcall as the same type as the function its jumping into (since its not
        # changing any registers\variables).
        xref_list = self.bv.get_code_refs(func.start)
        if len(xref_list) == 1:
            caller_func = xref_list[0].function
            if caller_func.mlil[0].operation == enums.MediumLevelILOperation.MLIL_TAILCALL:
                # If the first instruction is a tailcall, then change the functions' type to the called function type
                try:
                    function_type = Type.function(return_type, function_parameter_list, func_cc)
                    caller_func.set_user_type(function_type)
                    caller_func.name = '__j_' + func.name
                    return True
                except Exception as e:
                    print("Failed to fix the tailcall to function: ", func)
                    print(str(e))
                    return False
        return True

