"""
RUN INSTRUCTIONS: $python3 parser.py <PATH TO HEADER FILE>
"""

# Tree Sitter imports
import tree_sitter_c as tsc
from tree_sitter import Language, Parser
from typing import Generator

# YAML import
from yaml import dump

# Other imports
import sys
import re

###########################################################################
###--------------------------Global_Variables---------------------------###
###########################################################################
source = ""  # Source code string variable
prim_types = {  # (<sorted tuple of words in type>) : (<type name>, <longness value>, <signed?>)
    # float variants
    ("float",): ("float", 0, True),
    ("double",): ("float", 1, True),
    ("double", "long"): ("float", 2, True),
    # int variants
    ("int",): ("int", 0, True),
    ("short",): ("int", -1, True),
    ("long",): ("int", 1, True),
    ("long", "long"): ("int", 2, True),
    ("int", "signed"): ("int", 0, True),
    ("short", "signed"): ("int", -1, True),
    ("long", "signed"): ("int", 1, True),
    ("long", "long", "signed"): ("int", 2, True),
    ("int", "unsigned"): ("int", 0, False),
    ("short", "unsigned"): ("int", -1, False),
    ("long", "unsigned"): ("int", 1, False),
    ("long", "long", "unsigned"): ("int", 2, False),
    # char variants
    ("char",): ("char", 0, False),
    ("char", "signed"): ("char", 0, True),
    ("char", "unsigned"): ("char", 0, False),
}


###########################################################################
###---------------------------Parsing_Types-----------------------------###
###########################################################################
def parse_type(type: str, name: str) -> dict:
    prim_dict = {}
    if name == "void":
        prim_dict |= {"kind": "void"}
    elif type != "primitive_type" and type != "sized_type_specifier":
        prim_dict |= {"kind": "custom_type", "name": name}
    else:
        # Turn type name into tuple for hashing in prim_types
        type_toks = [tok for tok in name.split(" ") if tok]
        type_toks.sort()
        type_tup = tuple(type_toks)
        kind, longness, signed = prim_types[type_tup]
        # Append to dict necessary information based off of type
        prim_dict |= {"kind": kind}
        if longness != 0:
            prim_dict |= {"longness": longness}
        if kind == "char" and signed == True:
            prim_dict |= {"signed": True}
        if (kind == "int" or kind == "float") and signed == False:
            prim_dict |= {"unsigned": True}

    return prim_dict


###########################################################################
###----------------------Parsing_Translation_Unit-----------------------###
###########################################################################
def parse_translation_unit(tree) -> dict:
    yaml = {"kind": "translation_unit"}
    entities = []
    for node in tree.children:
        match node.type:
            case "declaration":
                entities.append(parse_decl(node))
            case "type_definition":
                entities.append(parse_typedef(node))
            case _:
                continue
    yaml |= {"entities": entities}
    return yaml


###########################################################################
###------------------------Parsing_Declarations-------------------------###
###########################################################################
def parse_decl(decl_node) -> dict:
    decl = {"kind": "declaration"}
    decl_type_node = decl_node.named_child(1)
    match decl_type_node.type:
        case "function_declarator":
            return decl | parse_func(decl_node)


###########################################################################
###-------------------------Parsing_Functions---------------------------###
###########################################################################
def parse_func(func_node) -> dict:
    # initialize source code, cursor, and dict
    cursor = func_node.walk()
    func = {}

    # extract and record return type
    cursor.goto_first_child()  # node: type: `return type`
    start = cursor.node.start_byte
    end = cursor.node.end_byte
    func |= {"type": parse_type(cursor.node.type, source[start:end])}

    # extract and record declarator
    cursor.goto_next_sibling()  # node: `function_declarator`
    cursor.goto_first_child()  # node: `declarator` : identifier
    start = cursor.node.start_byte
    end = cursor.node.end_byte
    cursor.goto_next_sibling()  # node: `parameter` : parameter list

    # extact and record params
    params = parse_params(cursor.node)
    func |= {
        "declarators": [
            {
                "kind": "declarator",
                "indirect_type": {"kind": "function", "params": params},
                "name": source[start:end],
            }
        ]
    }

    return func


###########################################################################
###-------------------------Parsing_Parameters--------------------------###
###########################################################################
def parse_params(params_node) -> list:
    params = []
    # loop through and record parameters
    for node in params_node.named_children:
        param = {"kind": "parameter"}
        decl_node = node.named_child(1)
        match decl_node.type:
            case "identifier":
                # extract and record param type
                type_node = node.named_child(0)
                start = type_node.start_byte
                end = type_node.end_byte
                param |= {"type": parse_type(type_node.type, source[start:end])}
                # extract and append param name
                start = decl_node.start_byte
                end = decl_node.end_byte
                param |= {"name": source[start:end]}
            case "pointer_declarator":
                cursor = node.walk()
                cursor.goto_first_child()  # node: `type`
                cursor.goto_next_sibling()  # node: `declarator` point_declarator
                param |= parse_pointer_param(cursor)
                # Travel down tree for param name
                cursor.goto_next_sibling()
                while cursor.goto_first_child():
                    cursor.goto_next_sibling()
                start = cursor.node.start_byte
                end = cursor.node.end_byte
                param |= {"name": re.sub(r"\*| ", "", source[start:end])}
            case _:
                print("WARNING Unhandled function parameter type: " + decl_node.type)
                exit(-1)
        params.append(param)

    return params


def parse_pointer_param(cursor) -> dict:
    match cursor.node.type:
        case "identifier":
            # travel up the tree for the type pointed to
            while True:
                cursor.goto_parent()
                if cursor.node.type != "pointer_declarator":
                    break
            cursor.goto_first_child()
            start = cursor.node.start_byte
            end = cursor.node.end_byte
            return {"type": parse_type(cursor.node.type, source[start:end])}
        case "pointer_declarator":
            cursor.goto_first_child()  # node: `*`
            cursor.goto_next_sibling()  # node: next declarator (either pointer_declarator or indentifier)
            return {"type": {"kind": "pointer"} | parse_pointer_param(cursor)}
        case _:
            print(
                "WARNING Unexpected declarator in parse_pointer_param(): "
                + cursor.node.type
            )
            exit(-1)


###########################################################################
###----------------------Parsing_Type_Definitions-----------------------###
###########################################################################
def parse_typedef(node) -> dict:
    typedef = {"kind": "declaration", "storage": ":typedef"}
    cursor = node.walk()
    # Extract type being renamed
    type_node = node.named_children[0]
    start = type_node.start_byte
    end = type_node.end_byte
    type = parse_type(type_node.type, source[start:end])
    # Extract renaming declarator
    decl_node = node.named_children[1]
    start = decl_node.start_byte
    end = decl_node.end_byte
    decl = {"kind": "declarator"}
    if decl_node.type == "pointer_declarator":
        decl |= {"indirect_type": parse_pointer_typdef(decl_node)}
    decl |= {"name": re.sub(r"\*| ", "", source[start:end])}
    # Append data to entry and return
    return typedef | {"type": type, "declarators": [decl]}


def parse_pointer_typdef(node) -> dict:
    match node.named_children[0].type:
        case "type_identifier":
            start = node.start_byte
            end = node.end_byte
            return {"kind": "pointer"}
        case "pointer_declarator":
            return {
                "kind": "pointer",
                "type": parse_pointer_typdef(node.named_children[0]),
            }
        case _:
            print(
                "WARNING Unexpected declarator in parse_pointer_typedef(): " + node.type
            )
            exit(-1)


###########################################################################
###----------------------------Main_Function----------------------------###
###########################################################################
def main():
    # Handle command line args
    args: int = len(sys.argv)
    if args != 2:
        print("INCORRECT NUMBER OF ARGS\n")
        print("Usage: python3 parser.py <header file path>")
        sys.exit(-1)

    header_path: str = str(sys.argv[1])

    # Read in file to string
    file = open(header_path)
    source = file.read()

    # Load language
    C_LANGUAGE = Language(tsc.language())

    # Create parser
    parser = Parser(C_LANGUAGE)

    # Parse header file and store tree
    tree = parser.parse(bytes(source, "utf-8"))

    # Generate yaml and print it
    yaml = parse_translation_unit(tree.root_node)
    print(dump(yaml, sort_keys=False, explicit_start=True).strip())
    # print(str(tree.root_node))


if __name__ == "__main__":
    main()

# EXAMPLE INPUT
# void foo(int a);
# int bar(double b);
# EXAMPLE AST
# (translation_unit
#     (declaration
#         type: (primitive_type)
#         declarator: (function_declarator
#             declarator: (identifier)
#             parameters: (parameter_list
#                 (parameter_declaration
#                     type: (primitive_type)
#                     declarator: (identifier)))))
#     (declaration
#         type: (primitive_type)
#         declarator: (function_declarator
#             declarator: (identifier)
#             parameters: (parameter_list
#                 (parameter_declaration
#                     type: (primitive_type)
#                     declarator: (identifier))))))


# # THIS CODE TRAVERSES ALL NODES (MIGHT NEED LATER SO DONT DELETE)
# def extract_nodes(cursor) -> Generator:
#     if not cursor.goto_first_child():
#         return
#     while True:
#         # print(cursor.node.type)
#         if cursor.node.type == "declaration" and is_function(cursor.node): yield cursor.node
#         elif cursor.goto_first_child(): continue
#         while not cursor.goto_next_sibling():
#             cursor.goto_parent()
#             if cursor.node.type == "translation_unit":
#                 return
