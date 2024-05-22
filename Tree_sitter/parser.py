import tree_sitter_c as tsc
from tree_sitter import Language, Parser, Node
from typing import Generator
import sys
from copy import *

source = ""  # Source code string variable



def extract_nodes(cursor) -> Generator:
    if not cursor.goto_first_child():
        return
    while True:
        # print(cursor.node.type)
        if cursor.node.type == "declaration" and is_function(cursor.node): yield cursor.node
        elif cursor.goto_first_child(): continue
        while not cursor.goto_next_sibling():
            cursor.goto_parent()
            if cursor.node.type == "translation_unit":
                return

def is_function(node) -> bool:
    declarator = node.named_child(1)
    return declarator.type == "function_declarator"

def emit_yaml(node) -> str:
    #initialize source code and 
    global source
    entry: str = "- Function:\n"

    # extract and append function name
    cursor = node.walk()
    cursor.goto_descendant(3)   # node: 'identifier' for function
    start = cursor.node.start_byte
    end = cursor.node.end_byte
    entry += "\tName: \"" + source[start:end] + "\"\n"

    # extract and append return type
    cursor.goto_parent()    # node: `function_declarator` for function
    cursor.goto_previous_sibling()  # node: `primitive_type` or return type identifier for function
    start = cursor.node.start_byte
    end = cursor.node.end_byte
    entry += "\tReturn_Type: \"" + source[start:end] + "\"\n"

    # extract and append parameters
    entry += "\tParameters:\n"
    cursor.goto_next_sibling()  # node: `function_declarator` for function
    cursor.goto_descendant(3)   # node: `parameter_list` for function (under `parameters` node)
    for node in cursor.node.named_children:
        type_node = node.named_children[0]
        name_node = node.named_children[1]
        # extract and append parameter name
        start = name_node.start_byte
        end = name_node.end_byte
        entry += "\t\tName: \"" + source[start:end] + "\"\n"
        # extract and append parameter type
        start = type_node.start_byte
        end = type_node.end_byte
        entry += "\t\tType: \"" + source[start:end] + "\"\n"


    # return final entry
    return entry


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

    # Initialize Cursor and run emit_yaml
    cursor = tree.walk()
    for node in extract_nodes(cursor): 
        print(emit_yaml(node))
    # pprint.pp(str(tree.root_node))


if __name__ == "__main__":
    main()


# (translation_unit (declaration type: (primitive_type) declarator: (function_declarator declarator: (identifier) parameters: (parameter_list (parameter_declaration type: (primitive_type) declarator: (identifier))))) (declaration type: (primitive_type) declarator: (function_declarator declarator: (identifier) parameters: (parameter_list (parameter_declaration type: (primitive_type) declarator: (identifier))))))
