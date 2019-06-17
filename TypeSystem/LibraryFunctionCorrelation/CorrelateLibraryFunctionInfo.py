# This module contains helper functions for correlating library function information obtained through Header Parsing
# into the library functions found in the examined binary view within BinaryNinja

from binaryninja import *
import Configuration
from . import NodeHandlers
from neo4j import GraphDatabase

driver = GraphDatabase.driver(Configuration.analysis_database_uri,
                              auth=(Configuration.analysis_database_user, Configuration.analysis_database_password),
                              max_connection_lifetime=60, max_connection_pool_size=1000,
                              connection_acquisition_timeout=30)


def correlate_entire_binary_view():
    for func in bv:
        func_name = func.name
        type_definition = dict()
        if not (func_name.startswith('sub_')):
            type_definition = NodeHandlers.get_type_definition(func_name)

        if type_definition:
            function_correlate(type_definition)
        else:
            print('Could not locate function ' + func.name + ' in the database')

def function_correlate(type_definition, key):
    """
    :param type_definition: A dict describing the type definition tree for the function.
                            Key is the hash of the function type (type_definition[key] is mapped to the function
                            definition).
    :return: True if successfully inserted definition into the bv, False otherwise.
    """
    # function_parameter_types = [(param_type, param_name), ...]
    function_parameter_types = [get_type_object(type_definition, param_key) for param_key in type_definition[key][1]]
    return_type = function_parameter_types[0]
    function_parameter_types = function_parameter_types[1:]

    func_params = [types.FunctionParameter(func_parameter[0], func_parameter[1]) for
                   func_parameter in function_parameter_types[1:]]

    # Function parameters are inserted in reverse order within the type_definition dict
    func_params.reverse()

    function_type = Type.function(return_type, func_params)

    try:
        current_function.set_user_type(function_type)
    except:
        print("Failed to set user type for function: ", function_type)
        return False

def get_type_object(type_definition, key)
    # Dispatch the correct method for parsing the specific type (typedef \ struct \ union \ enum)
    type_definition_field = type_definition[key][0][0]
    type_name_field = type_definition[key][0][1]

    if type_name_field == 'AnonymousStruct':
        return anonymous_struct_correlate(type_definition, key)
    if type_name_field.startswith('enum '):
        return enum_correlate(type_definition, key)
    if type_definition_field == 'Struct':
        return struct_correlate(type_definition, key)
    if type_definition_field == 'PointerTo':
        return pointer_correlate(type_definition, key)
    if type_definition_field == 'Union' or type_name_field == 'AnonymousUnion':
        return union_correlate(type_definition, key)

    return typedef_correlate(type_definition, key)


def struct_correlate(type_definition, key):
    # type_definition[key] =
    # [('Struct', '_SINGLE_LIST_ENTRY'), ['struct_field_type_hash', ...,]]

    struct = types.Structure()

    # add struct members
    for struct_field_hash in type_definition[key][1]:
        field_type = get_type_object(type_definition, struct_field_hash)
        struct.append(field_type, type_definition[struct_field_hash][0][1])

    try:
        bv.define_user_type(type_definition[key][0][1], types.Type.structure_type(struct))
    except:
        return False

    return bv.get_type_by_name(type_definition[key][0][1])

def union_correlate(type_definition, key):
    # type_definition[key] =
    # [('union _LARGE_INTEGER', '_LARGE_INTEGER'), ['union_field_type_hash', ...,]]
    # or
    # [('union _SE_TOKEN_USER::(anonymous at c:\WinHeaders\Unified/winnt.h:10756:5)', 'AnonymousUnion'),
    # ['union_field_type_hash', ...,]]

    struct = types.Structure()
    struct.type = enums.StructureType.UnionStructureType

    # add struct members
    for union_field_hash in type_definition[key][1]:
        field_type = get_type_object(type_definition, union_field_hash)
        struct.append(field_type, type_definition[union_field_hash][0][1])

    union_name = type_definition[key][0][0].split().split('::') if type_definition[key][0][1] == 'AnonymousUnion' \
                 else type_definition[key][0][1]

    try:
        bv.define_user_type(union_name, types.Type.structure_type(struct))
    except:
        return False

    return bv.get_type_by_name(type_definition[key][0][1])

def anonymous_struct_correlate(type_definition, key):



def enum_correlate(type_definition, key):
    # type_definition[key] =
    # [('enum _FILE_INFO_BY_HANDLE_CLASS', 'FILE_INFO_BY_HANDLE_CLASS'), ['sub_type_hash']]

    enum = types.Enumeration()

    for enum_literal_hash in type_definition[key][1]:
        # type_definition[enum_literal_hash] =
        # [('0', 'FileBasicInfo'), []]
        enum.append(type_definition[enum_literal_hash][0][1], type_definition[enum_literal_hash][0][0])

    try:
        bv.define_user_type(type_definition[key][0][1], types.Type.enumeration_type(bv.arch, enum))
    except:
        return False

    return bv.get_type_by_name(type_definition[key][0][1])


def pointer_correlate(type_definition, key):
    # type_definition[key] =
    # [('PointerTo', 'const unsigned char *'), ['sub_type_hash']]

    return get_type_object(type_definition, type_definition[key][1][0])


def typedef_correlate(type_definition, key):
    # type_definition[key] =
    # [('HANDLE', 'hFile'), ['sub_type_hash']]

    for sub_type_hash in type_definition[key][1]:
        if not get_type_object(type_definition, sub_type_hash):
            return False

    var_type, name = bv.parse_type_string("typedef " + type_definition[key][0] + " " + type_definition[key][1])

    try:
        bv.define_user_type(name, var_type)
    except:
        return False

    return bv.get_type_by_name(type_definition[key][0][1])
