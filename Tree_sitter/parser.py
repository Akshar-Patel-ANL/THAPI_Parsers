"""
RUN INSTRUCTIONS: $python3 parser.py <PATH TO HEADER FILE>
"""

import tree_sitter_c as tsc
from tree_sitter import Language, Parser
from typing import Generator
from yaml import dump
import sys
import re

###########################################################################
###--------------------------Global_Variables---------------------------###
###########################################################################
source = ""  # Source code string variable


###########################################################################
###---------------------------Parsing_Types-----------------------------###
###########################################################################
def parse_type(type: str, name: str) -> dict:
    prim_types = {  # (<sorted tuple of words in type>) : (<type name>, <longness value>, <signed?>)
        # float variants
        "float": ("float", 0, True),
        "double": ("float", 1, True),
        "long double": ("float", 2, True),
        # int variants
        "int": ("int", 0, True),
        "short": ("int", -1, True),
        "long": ("int", 1, True),
        "long long": ("int", 2, True),
        "signed int": ("int", 0, True),
        "signed short": ("int", -1, True),
        "signed long": ("int", 1, True),
        "signed long long": ("int", 2, True),
        "unsigned int": ("int", 0, False),
        "unsigned short": ("int", -1, False),
        "unsigned long": ("int", 1, False),
        "unsigned long long": ("int", 2, False),
        # char variants
        "char": ("char", 0, False),
        "signed char": ("char", 0, True),
        "unsigned char": ("char", 0, False),
    }
    prim_types_sanitized = {sanitize_type(k): v for k,v in prim_types.items()}

    prim_dict = {}
    if name == "void":
        prim_dict |= {"kind": "void"}
    elif type not in ["primitive_type", "sized_type_specifier"]:
        prim_dict |= {"kind": "custom_type", "name": name}
    else:
        # Turn type name into tuple for hashing in prim_types
        type_tup = sanitize_type(name)
        kind, longness, signed = prim_types_sanitized[type_tup]
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
    entities = []
    for node in tree.children:
        match node.type:
            case "declaration":
                entities.append(parse_decl(node))
            case "type_definition":
                entities.append(parse_typedef(node))
            case "comment":
                continue
            case _:
                raise NotImplementedError(
                    "WARNING Unhandled entity form in parse_translation_unit(): "
                    + node.type
                )
    return {"kind": "translation_unit", "entities": entities}


###########################################################################
###------------------------Parsing_Declarations-------------------------###
###########################################################################
def parse_decl(decl_node) -> dict:
    decl = {"kind": "declaration"}
    decl_type_node = decl_node.named_child(1)
    match decl_type_node.type:
        case "function_declarator":
            return decl | parse_func(decl_node)
        case _:
            print(
                "WARNING Unhandled delcaration form in parse_decl(): "
                + decl_type_node.type
            )


###########################################################################
###-------------------------Parsing_Functions---------------------------###
###########################################################################
def parse_func(func_node) -> dict:
    # initialize source code, cursor, and dict
    cursor = func_node.walk()
    func = {}

    # extract and record return type
    cursor.goto_first_child()  # node: type: `return type`
    func |= {"type": parse_type(cursor.node.type, extract_name(cursor.node))}

    # extract and record declarator
    cursor.goto_next_sibling()  # node: `function_declarator`
    cursor.goto_first_child()  # node: `declarator` : identifier
    decl_name = extract_name(cursor.node)
    cursor.goto_next_sibling()  # node: `parameter` : parameter list

    # extact and record params
    params = parse_params(cursor.node)
    func |= {
        "declarators": [
            {
                "kind": "declarator",
                "indirect_type": {"kind": "function", "params": params},
                "name": decl_name,
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
                param |= {"type": parse_type(type_node.type, extract_name(type_node))}
                # extract and append param name
                param |= {"name": extract_name(decl_node)}
            case "pointer_declarator":
                cursor = node.walk()
                cursor.goto_first_child()  # node: `type`
                cursor.goto_next_sibling()  # node: `declarator` point_declarator
                param |= parse_pointer_param(cursor)
                # Travel down tree for param name
                cursor.goto_next_sibling()
                while cursor.goto_first_child():
                    cursor.goto_next_sibling()
                param |= {"name": sanitize_pointer(extract_name(cursor.node))}
            case _:
                raise NotImplementedError(
                    "WARNING Unhandled function parameter type: " + decl_node.type
                )
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
            return {"type": parse_type(cursor.node.type, extract_name(cursor.node))}
        case "pointer_declarator":
            cursor.goto_first_child()  # node: `*`
            cursor.goto_next_sibling()  # node: next declarator (either pointer_declarator or indentifier)
            return {"type": {"kind": "pointer"} | parse_pointer_param(cursor)}
        case _:
            raise NotImplementedError(
                "WARNING Unexpected declarator in parse_pointer_param(): "
                + cursor.node.type
            )


###########################################################################
###----------------------Parsing_Type_Definitions-----------------------###
###########################################################################
def parse_typedef(node) -> dict:
    typedef = {"kind": "declaration", "storage": ":typedef"}
    # Extract type being renamed
    type_node = node.named_children[0]
    type = parse_type(type_node.type, extract_name(type_node))
    # Extract renaming declarator
    decl_node = node.named_children[1]
    decl = {"kind": "declarator"}
    if decl_node.type == "pointer_declarator":
        decl |= {"indirect_type": parse_pointer_typdef(decl_node)}
    decl |= {"name": sanitize_pointer(extract_name(decl_node))}
    # Append data to entry and return
    return typedef | {"type": type, "declarators": [decl]}


def parse_pointer_typdef(node) -> dict:
    match node.named_children[0].type:
        case "type_identifier":
            return {"kind": "pointer"}
        case "pointer_declarator":
            return {
                "kind": "pointer",
                "type": parse_pointer_typdef(node.named_children[0]),
            }
        case _:
            raise NotImplementedError(
                "WARNING Unexpected declarator in parse_pointer_typedef(): " + node.type
            )

###########################################################################
###--------------------------Helper_Functions---------------------------###
###########################################################################
def extract_name(node):
    start = node.start_byte
    end = node.end_byte
    return source[start:end]

def sanitize_type(name: str) -> tuple:
    toks = [tok for tok in name.split() if tok] # Removes empty strings that occasionally generate from split() here
    return tuple(sorted(toks))

def sanitize_pointer(name: str) -> str:
    return re.sub(r"\*| ", "", name)

###########################################################################
###----------------------------Main_Function----------------------------###
###########################################################################
if __name__ == "__main__":
    args = len(sys.argv)
    if args != 2:
        raise ValueError(
            "INCORRECT NUMBER OF ARGS\nUsage: python3 parser.py <header file path>"
        )

    header_path: str = str(sys.argv[1])
    with open(header_path, "r") as file:
        source = file.read()

    C_LANGUAGE = Language(tsc.language())
    parser = Parser(C_LANGUAGE)
    tree = parser.parse(bytes(source, "utf-8"))
    yaml = parse_translation_unit(tree.root_node)
    print(dump(yaml, sort_keys=False, explicit_start=True).strip())
    # print(str(tree.root_node))

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
#             cursor.goto_pare
