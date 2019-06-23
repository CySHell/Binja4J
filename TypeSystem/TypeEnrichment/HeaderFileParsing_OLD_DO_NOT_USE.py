from clang.cindex import *
from py2neo import *
import xxhash
import time
import threading

#########################################################################
#                                                                       #
#       Global Definitions                                              #
#                                                                       #
#########################################################################

POINTER_SIZE = {'x32': 4, 'x64': 8}
MAX_THREADS = 8

#########################################################################
#                                                                       #
#       Neo4j DB session creation                                       #
#                                                                       #
#########################################################################

# Create a session with the started local Neo4j DB, using the analysis_database_password 'user'. for more info on
# param search for py2neo.Graph()
graph = Graph(password='user')


# uncomment this line to delete the graph before each run of the script (good for testing purposes)
# graph.delete_all()


#########################################################################
#                                                                       #
#       HELPER FUNCTIONS                                                #
#                                                                       #
#########################################################################

def is_recursive_definition(node):
    """ Search for a circular definition of a type """
    relationship_count = graph.run(
        'MATCH analysis_database_path = (n)-[r*]->(n) where n.type_name = {TYPE_NAME} AND '
        'n.type_definition = {TYPE_DEFINITION} '
        'RETURN size(relationships(analysis_database_path))', TYPE_NAME=node['type_name'],
        TYPE_DEFINITION=node['type_definition'])

    return int(relationship_count.evaluate() or 0) > 0


#########################################################################

def merge_node(parent_node, relationship, node_label, **kwargs):
    """ Create the actual node\relationship in the Neo4j graph """
    if kwargs['type_name'] is None:
        kwargs['type_name'] = 'None'

    str_to_digest = str(kwargs['type_name']) + str(kwargs['type_definition'])
    xxhash_obj = xxhash.xxh64()
    xxhash_obj.update(str_to_digest)
    kwargs['HASH'] = xxhash_obj.hexdigest()

    current_node = Node(node_label, **kwargs)
    current_relationship = Relationship(parent_node, relationship, current_node)

    graph.merge(current_node, node_label, 'HASH')
    graph.merge(current_relationship, relationship)

    return current_node


#########################################################################

#########################################################################
#                                                                       #
#       TYPE HANDLING FUNCTIONS                                         #
#                                                                       #
#########################################################################

""" 
Each type handler deals with a specific clang AST type
:param type: clang.cindex.Type object
:param parent_node: py2neo.Node object , represents the parent of the current type node
:param relationship: str , determines the relationship label of the neo2py.Relationship object that will be created
"""


def handle_base_type(type, parent_node, relationship):
    args = {
        'type_name': str(type.kind).split('.')[1],
        'type_definition': type.spelling,
        'Size': type.get_size()
    }

    if type.spelling == 'VOID':
        args['Size'] = None
    merge_node(parent_node, relationship, 'Base_Type', **args)


#########################################################################

def handle_constant_array(type, parent_node, relationship):
    assert type.kind == TypeKind.CONSTANTARRAY

    args = {
        'type_name': type.spelling,
        'type_definition': type.element_type.spelling,
        'array_element_count': type.element_count,
        'Size': type.element_type.get_size() * type.element_count
    }

    current_node = merge_node(parent_node, relationship, str(type.kind).split('.')[1], **args)

    type_handles[type.element_type.kind](type.element_type, current_node, relationship)


#########################################################################


def handle_record(type, parent_node, relationship):
    assert type.kind == TypeKind.RECORD

    cursor_handles[type.get_declaration().kind](type.get_declaration(), parent_node, relationship)


#########################################################################

def handle_typedef(type, parent_node, relationship):
    assert type.kind == TypeKind.TYPEDEF

    cursor_handles[type.get_declaration().kind](type.get_declaration(), parent_node, relationship)


#########################################################################

def handle_pointer(type, parent_node, relationship):
    assert type.kind == TypeKind.POINTER or type.kind == TypeKind.LVALUEREFERENCE or \
           type.kind == TypeKind.RVALUEREFERENCE

    args = {
        'type_name': type.spelling,
        'type_definition': 'PointerTo',
        'Size': type.get_size()
    }

    current_node = merge_node(parent_node, relationship, str(type.kind).split('.')[1], **args)

    type_handles[type.get_pointee().kind](type.get_pointee(), current_node, 'PointerTo')


#########################################################################

def handle_unexposed(type, parent_node, relationship):
    assert type.kind == TypeKind.UNEXPOSED

    args = {
        'type_name': type.spelling,
        'type_definition': 'UNEXPOSED_TYPE',
        'Size': type.get_size()
    }

    merge_node(parent_node, relationship, str(type.kind).split('.')[1], **args)


#########################################################################

def handle_enum(type, parent_node, relationship):
    assert type.kind == TypeKind.ENUM

    print('error, should not reach handle_enum')


#########################################################################

def handle_function_proto(type, parent_node, relationship):
    assert type.kind == TypeKind.FUNCTIONPROTO

    args = {
        'type_name': type.spelling,
        'type_definition': type.spelling.split('__attribute__')[0],
        'Size': POINTER_SIZE['x64'],
        'function_argument_list': [str(i.spelling) for i in type.argument_types()]
    }

    current_node = merge_node(parent_node, relationship, str(type.kind).split('.')[1], **args)

    type_handles[type.get_result().kind](type.get_result(), current_node, 'Return_Type')

    for argument in type.argument_types():
        type_handles[argument.kind](argument, current_node, 'Function_Argument')


#########################################################################

def handle_function_no_proto(type, parent_node, relationship):
    assert type.kind == TypeKind.FUNCTIONNOPROTO

    args = {
        'type_name': type.spelling,
        'type_definition': 'FUNCTIONNOPROTO',
        'Size': POINTER_SIZE['x64'],
    }

    current_node = merge_node(parent_node, relationship, str(type.kind).split('.')[1], **args)

    type_handles[type.get_result().kind](type.get_result(), current_node, 'Return_Type')


#########################################################################

def handle_elaborated(type, parent_node, relationship):
    assert type.kind == TypeKind.ELABORATED

    cursor_handles[type.get_declaration().kind](type.get_declaration(), parent_node, relationship)


#########################################################################

def handle_incomplete_array(type, parent_node, relationship):
    assert type.kind == TypeKind.INCOMPLETEARRAY

    args = {
        'type_name': type.spelling,
        'type_definition': type.element_type.spelling,
        'Size': type.get_size()
    }

    current_node = merge_node(parent_node, relationship, str(type.kind).split('.')[1], **args)

    type_handles[type.element_type.kind](type.element_type, current_node, "Type_definition")


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


def cursor_handle_typedef_decl(cursor, parent_node, relationship):
    assert cursor.kind == CursorKind.TYPEDEF_DECL

    args = {
        'type_name': cursor.spelling,
        'type_definition': cursor.underlying_typedef_type.spelling
    }

    current_node = merge_node(parent_node, relationship, str(cursor.kind).split('.')[1], **args)

    underlying_typedef = cursor.underlying_typedef_type

    type_handles[underlying_typedef.kind](underlying_typedef, current_node, 'Type_Definition')


#########################################################################

def cursor_handle_field_decl(cursor, parent_node, relationship):
    assert cursor.kind == CursorKind.FIELD_DECL

    type_handles[cursor.type.kind](cursor.type, parent_node, 'Type_Definition')


#########################################################################

def cursor_handle_parm_decl(cursor, parent_node, relationship):
    assert cursor.kind == CursorKind.PARM_DECL

    args = {
        'type_name': cursor.spelling,
        'type_definition': cursor.type.spelling
    }

    current_node = merge_node(parent_node, relationship, str(cursor.kind).split('.')[1], **args)

    type_handles[cursor.type.kind](cursor.type, current_node, 'Type_Definition')


#########################################################################

def cursor_handle_struct_decl(cursor, parent_node, relationship):
    assert cursor.kind == CursorKind.STRUCT_DECL

    args = {
        'type_name': (cursor.type.spelling.split()[1].split('::')[0] + '_AnonymousStruct') if cursor.is_anonymous()
                                                                                           else cursor.spelling,
        'type_definition': 'Struct'
    }

    current_node = merge_node(parent_node, relationship, str(cursor.kind).split('.')[1], **args)

    if not (is_recursive_definition(current_node)):
        field_index = 0
        for field in cursor.type.get_fields():
            field_node = merge_node(current_node, 'Struct_Field', 'Struct_Field_DECL',
                                    **{'type_name': field.spelling, 'type_definition': field.type.spelling,
                                       'field_index': field_index})
            field_index += 1
            cursor_handles[field.kind](field, field_node, 'Type_Definition')


#########################################################################

def cursor_handle_function_decl(cursor, parent_node, relationship):
    assert cursor.kind == CursorKind.FUNCTION_DECL

    args = {
        'type_name': cursor.spelling,
        'type_definition': cursor.type.spelling,
        'function_argument_list': [str(i.spelling) for i in cursor.get_arguments()]
    }

    current_node = merge_node(parent_node, relationship, str(cursor.kind).split('.')[1], **args)

    type_handles[cursor.result_type.kind](cursor.result_type, current_node, 'Return_Type')

    for arg in cursor.get_arguments():
        cursor_handles[arg.kind](arg, current_node, 'Function_Argument')


#########################################################################

def cursor_handle_union_decl(cursor, parent_node, relationship):
    assert cursor.kind == CursorKind.UNION_DECL

    args = {
        'type_name': (cursor.type.spelling.split()[1].split('::')[0] + '_AnonymousUnion') if cursor.is_anonymous()
                                                                                          else cursor.spelling,
        'type_definition': cursor.type.spelling
    }

    current_node = merge_node(parent_node, relationship, str(cursor.kind).split('.')[1], **args)

    for field in cursor.type.get_fields():
        cursor_handles[field.kind](field, current_node, relationship)


#########################################################################

def cursor_handle_type_ref(cursor, parent_node, relationship):
    assert cursor.kind == CursorKind.TYPE_REF

    graph[cursor.type.kind] = cursor.type.spelling

    type_handles[cursor.type.kind](cursor.type, parent_node, relationship)


#########################################################################

def cursor_handle_var_decl(cursor, parent_node, relationship):
    assert cursor.kind == CursorKind.VAR_DECL

    args = {
        'type_name': cursor.spelling,
        'type_definition': cursor.type.spelling
    }

    current_node = merge_node(parent_node, relationship, str(cursor.kind).split('.')[1], **args)

    type_handles[cursor.type.kind](cursor.type, current_node, 'Type_Definition')


#########################################################################

def cursor_handle_do_nothing(cursor, parent_node, relationship):
    assert cursor.kind == CursorKind.UNEXPOSED_DECL or cursor.kind == CursorKind.CLASS_DECL

    pass


#    print('unexposed declaration, location:', cursor.location)


#########################################################################


def cursor_handle_enum_decl(cursor, parent_node, relationship):
    assert cursor.kind == CursorKind.ENUM_DECL

    args = {
        'type_name': cursor.type.spelling,
        'type_definition': 'ENUM'
    }

    current_node = merge_node(parent_node, relationship, str(cursor.kind).split('.')[1], **args)

    for enum_member in cursor.get_children():
        args = {
            'type_name': enum_member.spelling,
            'type_definition': str(enum_member.enum_value)
        }

        merge_node(current_node, 'ENUM_Definition', str(enum_member.kind).split('.')[1], **args)


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

# Create a UNIQUE constraint for each node type
node_label_list = []

for label in type_handles:
    node_label_list.append('CREATE CONSTRAINT ON (a: ' + label.name + ') ASSERT a.HASH IS UNIQUE')
for label in cursor_handles:
    node_label_list.append('CREATE CONSTRAINT ON (a: ' + label.name + ') ASSERT a.HASH IS UNIQUE')

for label in node_label_list:
    graph.run(label)


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
    header_file = 'c:\\WinHeaders\\Unified\\windows.h'

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

    parent_node = Node('Translation_Unit', type_name=node.spelling, type_definition='TU')  # root node of the tree
    graph.create(parent_node)

    # iterate all declaration in the header, parse them and populate the graph
    for c in node.get_children():
        cursor_handles[c.kind](c, parent_node, 'Top_Level_Declaration')

    end_time = time.time()
    print("Operation done in ", end_time - start_time, " seconds")


if __name__ == '__main__':
    main()
