import tree_sitter_c as tsc
from tree_sitter import Language, Parser, Node
from typing import Generator
import sys
from pprint import *


def abstract_nodes(cursor) -> Generator:
    while True:
        if cursor.goto_first_child():
            if cursor.node.is_named:
                yield cursor.node
        else:
            if not cursor.goto_next_sibling():
                break




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
    input: str = file.read()

    # Load language
    C_LANGUAGE = Language(tsc.language())

    # Create parser
    parser = Parser(C_LANGUAGE)

    # Parse header file and store tree
    tree = parser.parse(bytes(input, "utf-8"))

    # Initialize Cursor and run emit_yaml
    cursor = tree.walk()
    for node in abstract_nodes(cursor):
        print(node.id)
    # pprint.pp(str(tree.root_node))


if __name__ == "__main__":
    main()


# (translation_unit (declaration type: (primitive_type) declarator: (function_declarator declarator: (identifier) parameters: (parameter_list (parameter_declaration type: (primitive_type) declarator: (identifier))))) (declaration type: (primitive_type) declarator: (function_declarator declarator: (identifier) parameters: (parameter_list (parameter_declaration type: (primitive_type) declarator: (identifier))))))
