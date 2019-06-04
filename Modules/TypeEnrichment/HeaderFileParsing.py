from clang.cindex import *
from py2neo import *

#########################################################################
#                                                                       #
#       Global Definitions                                              #
#                                                                       #
#########################################################################

POINTER_SIZE = {'x32': 4, 'x64': 8}

#########################################################################
#                                                                       #
#       Neo4j DB session creation                                       #
#                                                                       #
#########################################################################

# Create a session with the started local Neo4j DB, using the password 'user'. for more info on param search for
# py2neo.Graph()
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
    relationship_count = graph.run('MATCH path = (n)-[r*]->(n) where n.name = {NAME} AND n.type_name = {TYPE_NAME} '
                                   'RETURN '
                                   'size(relationships(path))', NAME=node['name'], TYPE_NAME=node['type_name'])

    return int(relationship_count.evaluate() or 0) > 0


#########################################################################

def merge_node(parent_node, relationship, node_label, **kwargs):
    """ Create the actual node\relationship in the Neo4j graph """
    if kwargs['name'] == None:
        kwargs['name'] = 'None'

    kwargs['name'] = kwargs['type_name'] + '@' + kwargs['name']
    current_node = Node(node_label, **kwargs)
    current_relationship = Relationship(parent_node, relationship, current_node)

    graph.merge(current_node, node_label, 'name')
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
        'name': type.spelling,
        'type_name': str(type.kind).split('.')[1],
        'Size': type.get_size()
    }

    if type.spelling == 'VOID':
        args['Size'] = None
    merge_node(parent_node, relationship, 'Base_Type', **args)


#########################################################################

def handle_constant_array(type, parent_node, relationship):
    assert type.kind == TypeKind.CONSTANTARRAY

    args = {
        'name': type.spelling,
        'type_name': type.element_type.spelling,
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
    assert type.kind == TypeKind.POINTER

    args = {
        'name': type.spelling,
        'type_name': 'Pointer_To',
        'Size': type.get_size()
    }

    current_node = merge_node(parent_node, relationship, str(type.kind).split('.')[1], **args)

    type_handles[type.get_pointee().kind](type.get_pointee(), current_node, 'Pointer_To')


#########################################################################

def handle_unexposed(type, parent_node, relationship):
    assert type.kind == TypeKind.UNEXPOSED

    args = {
        'name': type.spelling,
        'type_name': 'UNEXPOSED_TYPE',
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
        'name': type.spelling,
        'type_name': 'Function_ProtoType',
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
        'name': type.spelling,
        'type_name': 'Function_No_ProtoType',
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
        'name': type.spelling,
        'type_name': type.element_type.spelling,
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
        'name': cursor.spelling,
        'type_name': cursor.underlying_typedef_type.spelling
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
        'name': cursor.spelling,
        'type_name': cursor.type.spelling
    }

    current_node = merge_node(parent_node, relationship, str(cursor.kind).split('.')[1], **args)

    type_handles[cursor.type.kind](cursor.type, current_node, 'Type_Definition')


#########################################################################

def cursor_handle_struct_decl(cursor, parent_node, relationship):
    assert cursor.kind == CursorKind.STRUCT_DECL

    args = {
        'name': cursor.spelling,
        'type_name': 'Struct'
    }

    current_node = merge_node(parent_node, relationship, str(cursor.kind).split('.')[1], **args)

    if not (is_recursive_definition(current_node)):
        for field in cursor.type.get_fields():
            field_node = merge_node(current_node, 'Struct_Field', 'Struct_Field_DECL',
                                    **{'name': field.spelling, 'type_name': field.type.spelling})
            cursor_handles[field.kind](field, field_node, 'Type_Definition')


#########################################################################

def cursor_handle_function_decl(cursor, parent_node, relationship):
    assert cursor.kind == CursorKind.FUNCTION_DECL

    args = {
        'name': cursor.spelling,
        'type_name': cursor.type.spelling,
        'function_argument_list': [str(i.spelling) for i in cursor.get_arguments()]
    }

    current_node = merge_node(parent_node, relationship, str(cursor.kind).split('.')[1], **args)

    type_handles[cursor.result_type.kind](cursor.result_type, current_node, 'Return_Type')

    for arg in cursor.get_arguments():
        cursor_handles[arg.kind](arg, current_node, 'Function_Argument')


#########################################################################

def cursor_handle_union_decl(cursor, parent_node, relationship):
    assert cursor.kind == CursorKind.UNION_DECL

    if str(cursor.type.spelling).startswith('_'):
        name = cursor.type.spelling
    else:
        name = str(cursor.type.spelling).split()[1].split(":")[0]

    args = {
        'name': name,
        'type_name': cursor.type.spelling
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
        'name': cursor.spelling,
        'type_name': cursor.type.spelling
    }

    current_node = merge_node(parent_node, relationship, str(cursor.kind).split('.')[1], **args)

    type_handles[cursor.type.kind](cursor.type, current_node, 'Type_Definition')


#########################################################################

def cursor_handle_unexposed_decl(cursor, parent_node, relationship):
    assert cursor.kind == CursorKind.UNEXPOSED_DECL

    pass


#    print('unexposed declaration, location:', cursor.location)


#########################################################################


def cursor_handle_enum_decl(cursor, parent_node, relationship):
    assert cursor.kind == CursorKind.ENUM_DECL

    args = {
        'name': cursor.type.spelling,
        'type_name': 'ENUM'
    }

    current_node = merge_node(parent_node, relationship, str(cursor.kind).split('.')[1], **args)

    for enum_member in cursor.get_children():
        args = {
            'name': enum_member.spelling,
            'type_name': str(enum_member.enum_value)
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
    # TypeKind.LVALUEREFERENCE
    # TypeKind.RVALUEREFERENCE
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
    CursorKind.UNEXPOSED_DECL: cursor_handle_unexposed_decl
}


#########################################################################
#                         MAIN                                          #
#########################################################################

def main():
    # TODO: Refactor this module to use the neo4j bolt driver, and improve the efficiency of cypher statements
    # Before using this module, install LLVM\Clang on your machine.
    # https://clang.llvm.org/get_started.html


    # path to libclang.so\dll file
    Config.set_library_file('C:\\Program Files\\LLVM\\bin\\libclang.dll')

    # c header file to parse
    # IMPORTANT: unless you want to deal with passing arguments regarding include files and dependancies, I suggest
    # putting all needed include files in the same directory as the header file you are trying to parse.
    header_file = 'c:\\WinHeaders\\Unified\\windows.h'


    index = Index.create()

    # Args for clang parser.
    # Change the --target argument to whatever system you want the header to apply to.
    args = ["-xc-header", "--target=x86_64-pc-windows-gnu", "-E"]

    # Create Translation unit from the header file
    tu = index.parse(header_file, args=args)
    if not tu:
        print("unable to load header file")

    node = tu.cursor

    parent_node = Node('Translation_Unit', name=node.spelling, type_name='TU')  # root node of the tree
    graph.create(parent_node)

    # iterate all declaration in the header, parse them and populate the graph
    for c in node.get_children():
        cursor_handles[c.kind](c, parent_node, 'Top_Level_Declaration')


if __name__ == '__main__':
    main()
