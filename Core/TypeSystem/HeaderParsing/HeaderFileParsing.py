from clang.cindex import *
from neo4j import GraphDatabase
from ...Common import GraphNodeInformation
import xxhash
import time
import csv
from .... import Configuration

#########################################################################
#                                                                       #
#       Global Definitions                                              #
#                                                                       #
#########################################################################

POINTER_SIZE = {'x32': 4, 'x64': 8}
MAX_THREADS = 8

# When encountering an incomplete array (arr[]) a size must be defined for BinaryNinja to accept it.
INCOMPLETEARRAY_SIZE = 1

# Anonymous definitions are given a pseudo random number to identify themselves
ANONYMOUS_INDEX = 0

#########################################################################
#                                                                       #
#       Init driver for neo4j DB                                        #
#                                                                       #
#########################################################################

driver = GraphDatabase.driver(Configuration.analysis_database_uri,
                              auth=(Configuration.analysis_database_user, Configuration.analysis_database_password),
                              max_connection_lifetime=60, max_connection_pool_size=1000,
                              connection_acquisition_timeout=30)

#########################################################################
#                                                                       #
#       csv files creation                                              #
#                                                                       #
#########################################################################

nodes_csv = open(Configuration.analysis_database_path + 'nodes.csv', 'w+', buffering=1, encoding='utf-8', newline='')
relationships_csv = open(Configuration.analysis_database_path + 'relationships.csv', 'w+', buffering=1,
                         encoding='utf-8', newline='')

nodes_csv_dict_writer = csv.DictWriter(nodes_csv, fieldnames=['TypeDefinition', 'TypeName', 'NodeLabel', 'Hash'])
nodes_csv_dict_writer.writeheader()
relationships_csv_dict_writer = csv.DictWriter(relationships_csv, fieldnames=['StartNodeHash', 'EndNodeHash',
                                                                              'RelationshipType'])
relationships_csv_dict_writer.writeheader()

#########################################################################
#                                                                       #
#       Cache init                                                      #
#                                                                       #
#########################################################################

nodes_cache = dict()  # {Hash: (TypeDefinition, TypeName, NodeLabel)}
# Relationship Cache is a set of strings representing each relationship
relationships_cache = set()  # {str(StartNodeHash + EndNodeHash + RelationshipType), ..,str(...)}


#########################################################################
#                                                                       #
#       HELPER FUNCTIONS                                                #
#                                                                       #
#########################################################################

def fix_array_definition(TypeDefinition, TypeName):
    # An array (both complete and incomplete definition) apear in the TypeDefinition instead of the TypeName,
    # for example: TypeDefinition: WORD [128] TypeName: PATCHARRAY.
    # For proper c syntax, the [] part is moved to the TypeName, as so:
    # TypeDefinition: WORD TypeName: PATCHARRAY[128] , so the final expression is "WORD PATCHARRAY[128]"

    if TypeDefinition.endswith(']'):
        array_def_index = TypeDefinition.rfind('[')
        if array_def_index:
            # store then array definition "[x]"
            array_definition = TypeDefinition[array_def_index:]
            # handle an incomplete array definition (for example "arr[]") by arbitrarily defining an array size
            if array_definition[1] == ']':
                array_definition = '[' + str(INCOMPLETEARRAY_SIZE) + ']'
            # remove the array definition from the TypeDefinition
            TypeDefinition = TypeDefinition[:array_def_index]
            # add the array definition to the TypeName
            TypeName += array_definition
        else:
            print("Failed to find an array definition within the type: ", TypeDefinition + TypeName)
            return False, False
    return TypeDefinition, TypeName


#########################################################################

def fix_anonymous_definition(string):
    # Anonymous definitions are given an arbitrary pseudo random number to designate their name.
    # The string argument is either a TypeDefinition or TypeName string.

    if '(anonymous' in string:
        start_index = string.rfind('(anonymous')
        end_index = start_index
        for chr in string[start_index:]:
            end_index += 1
            if chr == ')':
                break
        if end_index <= len(string):
            hash = get_string_hash(string[start_index:end_index])
            return string[:start_index] + hash + string[end_index:]
        else:
            print("Failed to parse anonymous definition: ", string)
            return False
    else:
        return string


#########################################################################


def is_recursive_definition(start_node_hash, end_node_hash, relationship_type):
    """ Search for a circular definition of a type """
    relationship_hash = start_node_hash + " " + end_node_hash + " " + relationship_type
    if relationship_hash in relationships_cache:
        return True
    return False


#########################################################################

def get_node_hash(kwargs):
    str_to_digest = str(kwargs['TypeName']) + str(kwargs['TypeDefinition']) + str(kwargs['NodeLabel'])
    xxhash_obj = xxhash.xxh64()
    xxhash_obj.update(str_to_digest)

    return str(xxhash_obj.hexdigest())


#########################################################################

def get_string_hash(string):
    xxhash_obj = xxhash.xxh64()
    xxhash_obj.update(string)

    return str(xxhash_obj.hexdigest())


#########################################################################

def merge_node(**kwargs):
    """
    Create the actual node\relationship in the csv.
    Two csv files exist: nodes.csv and relationships.csv .
    - nodes.csv has the format: <TypeDefinition>, <TypeName>, <NodeLabel>, <Hash>
    - relationships.csv has the format: <start node hash>, <end node hash>, <relationship type>
    """

    if kwargs['TypeName'] is None:
        kwargs['TypeName'] = 'None'

    kwargs['Hash'] = get_node_hash(kwargs)

    if '(*)' in kwargs['TypeDefinition']:
        # The type contains a pointer to a function prototype
        # args['TypeDefinition'] = HRESULT (*)(IRpcChannelBuffer *, RPCOLEMESSAGE *, ULONG *)
        # args['TypeName']       = SendReceive
        index = kwargs['TypeDefinition'].find('(*)')
        TypeDefinition = kwargs['TypeDefinition'][:index + 2] + kwargs['TypeName'] \
                         + ')' + kwargs['TypeDefinition'][index + 3:]
        kwargs['TypeName'] = ';'
        kwargs['TypeDefinition'] = TypeDefinition

    if not nodes_cache.get(kwargs['Hash']):
        nodes_cache.update({kwargs['Hash']: (kwargs['TypeDefinition'], kwargs['TypeName'], kwargs['NodeLabel'])})
    if kwargs['StartNodeHash'] != kwargs['Hash']:
        relationships_cache.add(kwargs['StartNodeHash'] + " " + kwargs['Hash'] + " " + kwargs['RelationshipType'])

    return kwargs['Hash']


#########################################################################

#########################################################################
#                                                                       #
#       TYPE HANDLING FUNCTIONS                                         #
#                                                                       #
#########################################################################

""" 
Each type handler deals with a specific clang AST type
:param type: clang.cindex.Type object
:param parent_node_hash: represents the parent of the current type node
:param relationship_type
"""


def handle_base_type(type, parent_node_hash, relationship_type):
    args = {
        'TypeName': str(type.kind).split('.')[1],
        'TypeDefinition': type.spelling,
        'StartNodeHash': parent_node_hash,
        'RelationshipType': 'ReturnType' if relationship_type == 'ReturnType' else 'BaseTypeDefinition',
        'NodeLabel': 'BaseType',
    }

    merge_node(**args)


#########################################################################

def handle_constant_array(type, parent_node_hash, relationship_type):
    assert type.kind == TypeKind.CONSTANTARRAY

    args = {
        'TypeName': type.spelling,
        'TypeDefinition': type.element_type.spelling,
        'StartNodeHash': parent_node_hash,
        'RelationshipType': relationship_type,
        'NodeLabel': str(type.kind).split('.')[1],
    }

    current_node_hash = merge_node(**args)

    type_handles[type.element_type.kind](type.element_type, current_node_hash, 'ArrayMember')


#########################################################################


def handle_record(type, parent_node_hash, relationship_type):
    assert type.kind == TypeKind.RECORD

    cursor_handles[type.get_declaration().kind](type.get_declaration(), parent_node_hash, relationship_type)


#########################################################################

def handle_typedef(type, parent_node_hash, relationship_type):
    assert type.kind == TypeKind.TYPEDEF

    cursor_handles[type.get_declaration().kind](type.get_declaration(), parent_node_hash, relationship_type)


#########################################################################

def handle_pointer(type, parent_node_hash, relationship_type):
    assert type.kind == TypeKind.POINTER or type.kind == TypeKind.LVALUEREFERENCE or \
           type.kind == TypeKind.RVALUEREFERENCE

    args = {
        'TypeName': type.spelling,
        'TypeDefinition': 'PointerTo',
        'StartNodeHash': parent_node_hash,
        'RelationshipType': relationship_type,
        'NodeLabel': str(type.kind).split('.')[1],
    }

    current_node_hash = merge_node(**args)

    type_handles[type.get_pointee().kind](type.get_pointee(), current_node_hash, 'PointerTo')


#########################################################################

def handle_unexposed(type, parent_node_hash, relationship_type):
    assert type.kind == TypeKind.UNEXPOSED

    args = {
        'TypeName': type.spelling,
        'TypeDefinition': 'UnexposedType',
        'StartNodeHash': parent_node_hash,
        'RelationshipType': 'UnKnown',
        'NodeLabel': str(type.kind).split('.')[1],
    }

    merge_node(**args)


#########################################################################

def handle_enum(type, parent_node, relationship):
    assert type.kind == TypeKind.ENUM

    print('error, should not reach handle_enum')


#########################################################################

def handle_function_proto(type, parent_node_hash, relationship_type):
    assert type.kind == TypeKind.FUNCTIONPROTO

    args = {
        'TypeName': type.spelling,
        'TypeDefinition': type.spelling.split('__attribute__')[0],
        'StartNodeHash': parent_node_hash,
        'RelationshipType': relationship_type,
        'NodeLabel': str(type.kind).split('.')[1],
    }

    current_node_hash = merge_node(**args)

    type_handles[type.get_result().kind](type.get_result(), current_node_hash, 'ReturnType')

    for argument in type.argument_types():
        type_handles[argument.kind](argument, current_node_hash, 'FunctionArgument')


#########################################################################

def handle_function_no_proto(type, parent_node_hash, relationship_type):
    assert type.kind == TypeKind.FUNCTIONNOPROTO

    args = {
        'TypeName': type.spelling,
        'TypeDefinition': 'FUNCTIONNOPROTO',
        'StartNodeHash': parent_node_hash,
        'RelationshipType': relationship_type,
        'NodeLabel': str(type.kind).split('.')[1],
    }

    current_node_hash = merge_node(**args)

    type_handles[type.get_result().kind](type.get_result(), current_node_hash, 'ReturnType')


#########################################################################

def handle_elaborated(type, parent_node_hash, relationship_type):
    assert type.kind == TypeKind.ELABORATED

    cursor_handles[type.get_declaration().kind](type.get_declaration(), parent_node_hash, relationship_type)


#########################################################################

def handle_incomplete_array(type, parent_node_hash, relationship_type):
    assert type.kind == TypeKind.INCOMPLETEARRAY

    args = {
        'TypeName': type.spelling,
        'TypeDefinition': type.element_type.spelling,
        'StartNodeHash': parent_node_hash,
        'RelationshipType': relationship_type,
        'NodeLabel': str(type.kind).split('.')[1],
    }

    current_node_hash = merge_node(**args)

    type_handles[type.element_type.kind](type.element_type, current_node_hash, "ArrayElement")


#########################################################################

#########################################################################
#                                                                       #
#       CURSOR HANDLING FUNCTIONS                                       #
#                                                                       #
#########################################################################

""" 
Each cursor handler deals with a specific clang AST type
:param type: clang.cindex.Cursor object
:param parent_node: py2neo.Node object , represents the parent of the current type node
:param relationship: str , determines the relationship label of the neo2py.Relationship object that will be created
"""


def cursor_handle_typedef_decl(cursor, parent_node_hash, relationship_type):
    assert cursor.kind == CursorKind.TYPEDEF_DECL

    args = {
        'TypeName': cursor.spelling,
        'TypeDefinition': cursor.underlying_typedef_type.spelling,
        'StartNodeHash': parent_node_hash,
        'RelationshipType': relationship_type,
        'NodeLabel': str(cursor.kind).split('.')[1],
    }

    current_node_hash = merge_node(**args)

    underlying_typedef = cursor.underlying_typedef_type

    type_handles[underlying_typedef.kind](underlying_typedef, current_node_hash, 'TypeDef')


#########################################################################

def cursor_handle_field_decl(cursor, parent_node_hash, relationship_type):
    assert cursor.kind == CursorKind.FIELD_DECL

    type_handles[cursor.type.kind](cursor.type, parent_node_hash, 'FieldDef')


#########################################################################

def cursor_handle_parm_decl(cursor, parent_node_hash, relationship_type):
    assert cursor.kind == CursorKind.PARM_DECL

    args = {
        'TypeName': cursor.spelling,
        'TypeDefinition': cursor.type.spelling,
        'StartNodeHash': parent_node_hash,
        'RelationshipType': relationship_type,
        'NodeLabel': str(cursor.kind).split('.')[1],
    }

    current_node_hash = merge_node(**args)

    type_handles[cursor.type.kind](cursor.type, current_node_hash, 'FunctionParamDef')


#########################################################################

def cursor_handle_struct_decl(cursor, parent_node_hash, relationship_type):
    assert cursor.kind == CursorKind.STRUCT_DECL

    args = {
        'TypeName': (cursor.type.spelling.split()[1].split('::')[0] + '_AnonymousStruct') if cursor.is_anonymous()
        else cursor.spelling,
        'TypeDefinition': 'struct',
        'StartNodeHash': parent_node_hash,
        'RelationshipType': relationship_type,
        'NodeLabel': str(cursor.kind).split('.')[1],
    }

    if not is_recursive_definition(args['StartNodeHash'], get_node_hash(args), args['RelationshipType']):
        current_node_hash = merge_node(**args)
        field_list = list(cursor.type.get_fields())
        if not field_list:
            # For some struct_decl, clang doesn't contain fields, but it does recognize the children of the node,
            # probably due to a bug.
            # if get_fields() doesn't work, just get the children of the node and treat them as the fields.
            # example struct that behaves like this: struct _EXCEPTION_POINTERS
            field_list = list(cursor.get_children())
        for field in field_list:
            args = {
                'TypeName': field.spelling,
                'TypeDefinition': field.type.spelling,
                'StartNodeHash': current_node_hash,
                'RelationshipType': 'FieldDef',
                'NodeLabel': 'StructFieldDecl',
            }
            field_node_hash = merge_node(**args)
            cursor_handles[field.kind](field, field_node_hash, 'FieldDef')


#########################################################################

def cursor_handle_function_decl(cursor, parent_node_hash, relationship_type):
    assert cursor.kind == CursorKind.FUNCTION_DECL

    args = {
        'TypeName': cursor.spelling,
        'TypeDefinition': cursor.displayname,
        'StartNodeHash': parent_node_hash,
        'RelationshipType': relationship_type,
        'NodeLabel': str(cursor.kind).split('.')[1],
    }

    current_node_hash = merge_node(**args)

    type_handles[cursor.result_type.kind](cursor.result_type, current_node_hash, 'ReturnType')

    for arg in cursor.get_arguments():
        cursor_handles[arg.kind](arg, current_node_hash, 'FunctionArgument')


#########################################################################

def cursor_handle_union_decl(cursor, parent_node_hash, relationship_type):
    assert cursor.kind == CursorKind.UNION_DECL

    args = {
        'TypeName': (cursor.type.spelling.split()[1].split('::')[0] + '_AnonymousUnion') if cursor.is_anonymous()
        else cursor.spelling,
        'TypeDefinition': cursor.type.spelling,
        'StartNodeHash': parent_node_hash,
        'RelationshipType': relationship_type,
        'NodeLabel': str(cursor.kind).split('.')[1],
    }

    current_node_hash = merge_node(**args)

    for field in cursor.type.get_fields():
        cursor_handles[field.kind](field, current_node_hash, 'UnionField')


#########################################################################

def cursor_handle_type_ref(cursor, parent_node_hash, relationship_type):
    assert cursor.kind == CursorKind.TYPE_REF

    print("Reached a type_ref, parent node hash is: ", parent_node_hash)

    type_handles[cursor.type.kind](cursor.type, parent_node_hash, 'TypeRef')


#########################################################################

def cursor_handle_var_decl(cursor, parent_node_hash, relationship_type):
    assert cursor.kind == CursorKind.VAR_DECL

    args = {
        'TypeName': cursor.spelling,
        'TypeDefinition': cursor.type.spelling,
        'StartNodeHash': parent_node_hash,
        'RelationshipType': relationship_type,
        'NodeLabel': str(cursor.kind).split('.')[1],
    }

    current_node_hash = merge_node(**args)

    type_handles[cursor.type.kind](cursor.type, current_node_hash, 'VariableDef')


#########################################################################

def cursor_handle_do_nothing(cursor, parent_node, relationship):
    assert cursor.kind == CursorKind.UNEXPOSED_DECL or cursor.kind == CursorKind.CLASS_DECL

    pass


#########################################################################


def cursor_handle_enum_decl(cursor, parent_node_hash, relationship_type):
    assert cursor.kind == CursorKind.ENUM_DECL

    args = {
        'TypeName': cursor.type.spelling,
        'TypeDefinition': 'Enumeration',
        'StartNodeHash': parent_node_hash,
        'RelationshipType': relationship_type,
        'NodeLabel': str(cursor.kind).split('.')[1],
    }

    current_node_hash = merge_node(**args)

    for enum_member in cursor.get_children():
        args = {
            'TypeName': enum_member.spelling,
            'TypeDefinition': str(enum_member.enum_value),
            'StartNodeHash': current_node_hash,
            'RelationshipType': 'EnumDefinition',
            'NodeLabel': str(enum_member.kind).split('.')[1],
        }
        merge_node(**args)


#########################################################################
#               Handler function pointers                               #
#########################################################################

type_handles = {
    # TypeKind.INVALID: handle_invalid(),
    TypeKind.UNEXPOSED: handle_unexposed,
    TypeKind.VOID: handle_base_type,
    TypeKind.BOOL: handle_base_type,
    TypeKind.CHAR_U: handle_base_type,
    TypeKind.UCHAR: handle_base_type,
    TypeKind.CHAR16: handle_base_type,
    TypeKind.CHAR32: handle_base_type,
    TypeKind.USHORT: handle_base_type,
    TypeKind.UINT: handle_base_type,
    TypeKind.ULONG: handle_base_type,
    TypeKind.ULONGLONG: handle_base_type,
    TypeKind.UINT128: handle_base_type,
    TypeKind.CHAR_S: handle_base_type,
    TypeKind.SCHAR: handle_base_type,
    TypeKind.WCHAR: handle_base_type,
    TypeKind.SHORT: handle_base_type,
    TypeKind.INT: handle_base_type,
    TypeKind.LONG: handle_base_type,
    TypeKind.LONGLONG: handle_base_type,
    TypeKind.INT128: handle_base_type,
    TypeKind.FLOAT: handle_base_type,
    TypeKind.DOUBLE: handle_base_type,
    TypeKind.LONGDOUBLE: handle_base_type,
    # TypeKind.NULLPTR
    # TypeKind.OVERLOAD
    # TypeKind.DEPENDENT
    # TypeKind.OBJCID
    # TypeKind.OBJCCLASS
    # TypeKind.OBJCSEL
    TypeKind.FLOAT128: handle_base_type,
    TypeKind.COMPLEX: handle_base_type,
    TypeKind.POINTER: handle_pointer,
    # TypeKind.BLOCKPOINTER
    TypeKind.LVALUEREFERENCE: handle_pointer,
    TypeKind.RVALUEREFERENCE: handle_pointer,
    TypeKind.RECORD: handle_record,
    TypeKind.ENUM: handle_enum,
    TypeKind.TYPEDEF: handle_typedef,
    # TypeKind.OBJCINTERFACE
    # TypeKind.OBJCOBJECTPOINTER
    TypeKind.FUNCTIONNOPROTO: handle_function_no_proto,
    TypeKind.FUNCTIONPROTO: handle_function_proto,
    TypeKind.CONSTANTARRAY: handle_constant_array,
    # TypeKind.VECTOR
    TypeKind.INCOMPLETEARRAY: handle_incomplete_array,
    # TypeKind.VARIABLEARRAY
    # TypeKind.DEPENDENTSIZEDARRAY
    # TypeKind.MEMBERPOINTER
    # TypeKind.AUTO
    TypeKind.ELABORATED: handle_elaborated
}

cursor_handles = {
    CursorKind.TYPEDEF_DECL: cursor_handle_typedef_decl,
    CursorKind.TYPE_REF: cursor_handle_type_ref,
    CursorKind.STRUCT_DECL: cursor_handle_struct_decl,
    CursorKind.FUNCTION_DECL: cursor_handle_function_decl,
    CursorKind.PARM_DECL: cursor_handle_parm_decl,
    CursorKind.FIELD_DECL: cursor_handle_field_decl,
    CursorKind.UNION_DECL: cursor_handle_union_decl,
    CursorKind.VAR_DECL: cursor_handle_var_decl,
    CursorKind.ENUM_DECL: cursor_handle_enum_decl,
    CursorKind.UNEXPOSED_DECL: cursor_handle_do_nothing,
    CursorKind.CLASS_DECL: cursor_handle_do_nothing,
}


#########################################################################
#                         MAIN                                          #
#########################################################################

def main():
    # TODO: Refactor this module to use the neo4j bolt driver, and improve the efficiency of cypher statements
    # Before using this module, install LLVM\Clang on your machine.
    # https://clang.llvm.org/get_started.html

    start_time = time.time()

    # analysis_database_path to libclang.so\dll file
    Config.set_library_file('C:\\Program Files\\LLVM\\bin\\libclang.dll')

    # c header file to parse
    # IMPORTANT: unless you want to deal with passing clang arguments regarding include files and dependancies, I
    # suggest putting all needed include files in the same directory as the header file you are trying to parse.

    header_file = 'c:\\WinHeaders\\Unified\\MsHTML.h'

    index = Index.create()

    # Args for clang parser:
    #   -xc-header : tell clang that you're compiling a c header file
    #   --target : Change the --target argument to whatever system you want the header to apply to.
    #   -E : only use the pre-processor, don't attempt to compile

    args = ["-xc-header", "--target=x86_64-pc-windows-gnu", "-E"]

    # Create Translation unit from the header file
    tu = index.parse(header_file, args=args)
    if not tu:
        print("unable to load header file")

    node = tu.cursor

    args = {
        'TypeName': node.spelling,
        'TypeDefinition': 'TranslationUnit',
        'StartNodeHash': 'TU' + node.spelling,
        'RelationshipType': 'TranslationUnit',
        'NodeLabel': 'TranslationUnit',
    }

    merge_node(**args)

    # iterate all declaration in the header, parse them and populate the graph
    for c in node.get_children():
        cursor_handles[c.kind](c, args['StartNodeHash'], 'Top_Level_Declaration')

    # Init UNIQUE constraint for each node type
    node_label_list = set()
    for item in nodes_cache.values():
        node_label_list.update({item[2], })

    with driver.session() as session:
        for node_label in node_label_list:
            session.run('CREATE CONSTRAINT ON (a:' + node_label + ') ASSERT a.Hash IS UNIQUE')

    # write information to csv
    for node in nodes_cache:
        TypeDefinition, TypeName = fix_array_definition(nodes_cache[node][0], nodes_cache[node][1])

        TypeDefinition = fix_anonymous_definition(TypeDefinition)
        TypeName = fix_anonymous_definition(TypeName)

        nodes_csv_dict_writer.writerow({'TypeDefinition': TypeDefinition, 'TypeName': TypeName,
                                        'NodeLabel': nodes_cache[node][2], 'Hash': str(node)})
    for relationship in relationships_cache:
        start_node_hash, end_node_hash, relationship_type = relationship.split()
        relationships_csv_dict_writer.writerow({'StartNodeHash': start_node_hash,
                                                'EndNodeHash': end_node_hash,
                                                'RelationshipType': relationship_type})

    # Batch insert CSV into neo4j
    with driver.session() as session:

        filename = '\'file:/nodes.csv\' '
        print('Now Processing: ', filename)
        session.run("USING PERIODIC COMMIT 1000 "
                    "LOAD CSV WITH HEADERS FROM " + filename + "AS row "
                                                               "CALL apoc.merge.node([row['NodeLabel']], {Hash: row['Hash']}, row) yield node "
                                                               "RETURN true "
                    )

        filename = '\'file:/relationships.csv\' '
        print('Now Processing: ', filename)

        node_label_mapping = GraphNodeInformation.get_node_label_map(driver)

        session.run("USING PERIODIC COMMIT 5000 "
                    "LOAD CSV WITH HEADERS FROM " + filename + "AS rel_row "
                                                               "CALL apoc.search.node({node_label_mapping}, 'exact', rel_row.StartNodeHash ) yield node as start "
                                                               "CALL apoc.search.node({node_label_mapping}, 'exact', rel_row.EndNodeHash ) yield node as end "
                                                               "CALL apoc.merge.relationship(start, rel_row.RelationshipType,"
                                                               "{StartNodeHash: start.Hash, EndNodeHash: end.Hash, "
                                                               "RelationshipType: rel_row.RelationshipType}, rel_row, end) yield rel "
                                                               "RETURN True ", node_label_mapping=node_label_mapping)

        session.sync()
        session.close()

    nodes_csv.close()
    relationships_csv.close()

    end_time = time.time()
    print("Operation done in ", end_time - start_time, " seconds")


if __name__ == '__main__':
    main()
