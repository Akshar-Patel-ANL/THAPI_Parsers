"""
RUN INSTRUCTIONS: $python3 parser.py <PATH TO HEADER FILE>
"""

import tree_sitter_c as tsc
from tree_sitter import Language, Parser
from typing import Generator
from yaml import dump
import sys
import re

source = ""  # Source code string variable

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


###########################################################################
###----------------------parsing_translation_unit-----------------------###
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
###------------------------parsing_declarations-------------------------###
###########################################################################
def parse_decl(decl_node) -> dict:
    global source
    decl = {"kind": "declaration"}
    decl_type_node = decl_node.named_child(1)
    match decl_type_node.type:
        case "function_declarator":
            return decl | parse_func(decl_node)


###########################################################################
###-------------------------parsing_functions---------------------------###
###########################################################################
def parse_func(func_node) -> dict:
    # initialize source code, cursor, and dict
    global source
    cursor = func_node.walk()
    func = {}

    # extract and record return type
    cursor.goto_first_child()  # node: type: `return type`
    start = cursor.node.start_byte
    end = cursor.node.end_byte
    func |= {"type": {"kind": source[start:end]}}

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
                "name" : source[start:end]
            }
        ]
    }

    return func


###########################################################################
###-------------------------parsing_parameters--------------------------###
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
                if type_node.type == "primitive_tive":
                    param |= {"type" : {"kind" : source[start:end]}}
                else:
                    param |= {"type" : {"kind" : "custom_type", "name" : source[start:end]}}
                # extract and append param name
                start = decl_node.start_byte
                end = decl_node.end_byte
                param |= {"name": source[start:end]}
            case "pointer_declarator":
                cursor = node.walk()
                cursor.goto_first_child()  # node: `type`
                cursor.goto_next_sibling()  # node: `declarator`: point_declarator
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
            global source
            # travel up the tree for the type pointed to
            while True:
                cursor.goto_parent()
                if cursor.node.type != "pointer_declarator":
                    break
            cursor.goto_first_child()
            start = cursor.node.start_byte
            end = cursor.node.end_byte
            return {"type": {"kind": source[start:end]}}
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
###----------------------parsing_type_definitions-----------------------###
###########################################################################
def parse_typedef(node) -> dict:
    global source
    typedef = {"kind": "declaration", "storage": ":typedef"}
    cursor = node.walk()
    # Extract type being renamed
    type_node = node.named_children[0]
    start = type_node.start_byte
    end = type_node.end_byte
    match type_node.type:
        case "type_identifier":
            type = {"kind": "custom_type", "name": source[start:end]}
        case "primitive_type": 
            type = {"kind": source[start:end]}
        case _:
            print(
                "WARNING Unexpected type being renamed in parse_typedef(): "
                + type_node.type
            )
            exit(-1)
    # Extract renaming declarator
    decl_node = node.named_children[1]
    start = decl_node.start_byte
    end = decl_node.end_byte
    decl = {"kind": "declarator", "name": source[start:end]}
    # Append data to entry and return
    return typedef | {"type": type, "declarators": [decl]}


###########################################################################
###----------------------------main_function----------------------------###
###########################################################################
def main():
    global source
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
