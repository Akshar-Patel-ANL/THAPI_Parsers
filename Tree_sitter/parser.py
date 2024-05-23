import tree_sitter_c as tsc
from tree_sitter import Language, Parser
from typing import Generator
from yaml import dump
import sys

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


def parse_translation_unit(tree) -> dict:
    yaml = {"kind": "translation_unit"}
    entities = []
    for node in tree.children:
        match node.type:
            case "declaration":
                entities.append(parse_decl(node))
            case _:
                continue
    yaml["entities"] = entities
    return yaml


# def is_function(node) -> bool:
#     declarator = node.named_child(1)
#     return declarator.type == "function_declarator"


def emit_yaml(node) -> str:
    match node,named_child(1).type:
        case "function_declarator":
            return emit_yaml_func(node)
        case _:
            return "NOT SUPPORTED"
        
def parse_decl(node) -> dict:
    decl = {"kind" : "declaration"}
    match node.named_child(1).type:
        case "function_declarator":
            return parse_func(node, decl)

def parse_func(node, decl) -> dict:
    # initialize source code and 
    global source
    cursor = node.walk()

    # extract and record return type
    cursor.goto_descendant(1)   # node: type: `return type`
    start = cursor.node.start_byte
    end = cursor.node.end_byte
    decl["type"] = {"kind" : source[start:end]}

    # extract and record declarator

    params = []
    cursor.goto_next_sibling()  # node: `function_declarator`
    cursor.goto
    decl["declarators"] = [{"kind" : "declarator",
                            "indirect_type" :
                                {"kind" : "function",
                                 "params": params}}]


    # # extract and append function name
    # cursor.goto_descendant(3)   # node: 'identifier' for function
    # start = cursor.node.start_byte
    # end = cursor.node.end_byte
    # entry += "\tName: \"" + source[start:end] + "\"\n"

    # # extract and append return type
    # cursor.goto_parent()    # node: `function_declarator` for function
    # cursor.goto_previous_sibling()  # node: `primitive_type` or return type identifier for function
    # start = cursor.node.start_byte
    # end = cursor.node.end_byte
    # entry += "\tReturn_Type: \"" + source[start:end] + "\"\n"

    # # extract and append parameters
    # entry += "\tParameters:\n"
    # cursor.goto_next_sibling()  # node: `function_declarator` for function
    # cursor.goto_descendant(3)   # node: `parameter_list` for function (under `parameters` node)
    # for node in cursor.node.named_children:
    #     type_node = node.named_children[0]
    #     name_node = node.named_children[1]
    #     # extract and append parameter name
    #     start = name_node.start_byte
    #     end = name_node.end_byte
    #     entry += "\t\tName: \"" + source[start:end] + "\"\n"
    #     # extract and append parameter type
    #     start = type_node.start_byte
    #     end = type_node.end_byte
    #     entry += "\t\tType: \"" + source[start:end] + "\"\n"


    # # return final entry
    # return entry



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
    print(dump(yaml))
    # print(str(tree.root_node))

if __name__ == "__main__":
    main()


# (translation_unit (declaration type: (primitive_type) declarator: (function_declarator declarator: (identifier) parameters: (parameter_list (parameter_declaration type: (primitive_type) declarator: (identifier))))) (declaration type: (primitive_type) declarator: (function_declarator declarator: (identifier) parameters: (parameter_list (parameter_declaration type: (primitive_type) declarator: (identifier))))))
