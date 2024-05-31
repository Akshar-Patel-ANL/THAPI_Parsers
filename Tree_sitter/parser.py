"""
RUN INSTRUCTIONS: $python3 parser.py <PATH TO HEADER FILE>
"""

import tree_sitter_c
import tree_sitter
from yaml import dump
import sys
import re


###########################################################################
###--------------------------Global_Variables---------------------------###
###########################################################################
header_source = ""  # Source code string variable


###########################################################################
###--------------------------Helper_Functions---------------------------###
###########################################################################
def extract_src_text(node):
    start = node.start_byte
    end = node.end_byte
    return header_source[start:end].decode()  # header_source is a global variable


def sanitize_type(name: str) -> tuple:
    return tuple(sorted(name.split()))


def sanitize_pointer(name: str) -> str:
    return re.sub(r"\*| ", "", name)


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
    prim_types_sanitized = {sanitize_type(k): v for k, v in prim_types.items()}

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
                    f"Unhandled entity form in parse_translation_unit(): #{node.type}"
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
            print(f"Unhandled delcaration form in parse_decl(): #{decl_type_node.type}")


###########################################################################
###-------------------------Parsing_Functions---------------------------###
###########################################################################
def parse_func(func_node) -> dict:
    # initialize source code, cursor, and dict
    cursor = func_node.walk()
    func = {}

    # extract and record return type
    cursor.goto_first_child()  # node: type: `return type`
    func |= {"type": parse_type(cursor.node.type, extract_src_text(cursor.node))}

    # extract and record declarator
    cursor.goto_next_sibling()  # node: `function_declarator`
    cursor.goto_first_child()  # node: `declarator` : identifier
    decl_name = extract_src_text(cursor.node)
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
        type_node = node.children[0]
        decl_node = node.children[1]
        match types := [child_node.type for child_node in node.children]:
            case (
                ["primitive_type", "identifier"]
                | ["sized_type_specifier", "identifier"]
                | ["type_identifier", "identifier"]
            ):
                type_dict = parse_type(types[0], extract_src_text(type_node))
                decl_name = extract_src_text(decl_node)
            case (
                ["primitive_type", "pointer_declarator"]
                | ["sized_type_specifier", "pointer_declarator"]
                | ["type_identifier", "pointer_declarator"]
            ):
                decl_name, type_dict = parse_pointer_param(
                    parse_type(types[0], extract_src_text(type_node)), decl_node
                )
            case _:
                raise NotImplementedError(
                    f"Unhandled function parameter type in parser_params(): #{types}"
                )
        params.append({"kind": "parameter", "type": type_dict, "name": decl_name})

    return params


def parse_pointer_param(type, node) -> tuple:
    match types := [child_node.type for child_node in node.children]:
        case ["*", "identifier"]:
            return (
                extract_src_text(node.children[1]),
                {"kind": "pointer", "type": type},
            )
        case ["*", "pointer_declarator"] | ["primitive_type", "pointer_declarator"]:
            decl_name, type_dict = parse_pointer_param(type, node.children[1])
            return (decl_name, {
                "kind": "pointer",
                "type": type_dict})
        case _:
            raise NotImplementedError(
                f"Unexpected declarator in parse_pointer_param(): #{types}"
            )


###########################################################################
###----------------------Parsing_Type_Definitions-----------------------###
###########################################################################
def parse_typedef(node) -> dict:
    type_node = node.children[1]
    type_dict = parse_type(type_node.type, extract_src_text(type_node))
    decl_node = node.children[2]
    match types := [child_node.type for child_node in node.children]:
        case (
            ["typedef", "primitive_type", "type_identifier", ";"]
            | ["typedef", "type_identifier", "type_identifier", ";"]
            | ["typedef", "sized_type_specifier", "type_identifier", ";"]
        ):
            decl = {"kind": "declarator", "name": extract_src_text(decl_node)}
        case (
            ["typedef", "primitive_type", "pointer_declarator", ";"]
            | ["typedef", "type_identifier", "pointer_declarator", ";"]
            | ["typedef", "sized_type_specifier", "pointer_declarator", ";"]
        ):
            decl_name, pointer_dict = parse_pointer_typedef(decl_node)
            decl = {
                "kind": "declarator",
                "indirect_type": pointer_dict,
                "name": decl_name,
            }
        case _:
            raise NotImplementedError(f"Unhandled case in parse_typdef(): #{types}")
    return {
        "kind": "declaration",
        "storage": ":typedef",
        "type": type_dict,
        "declarators": [decl],
    }


def parse_pointer_typedef(node) -> tuple:
    match types := [child_node.type for child_node in node.children]:
        case ["*", "type_identifier"]:
            return (extract_src_text(node.children[1]), {"kind": "pointer"})
        case ["*", "pointer_declarator"]:
            decl_name, pointer_dict = parse_pointer_typedef(node.children[1])
            return (
                decl_name,
                {
                    "kind": "pointer",
                    "type": pointer_dict,
                },
            )
        case _:
            raise NotImplementedError(
                f"Unexpected declarator in parse_pointer_typedef(): #{types}"
            )


###########################################################################
###----------------------------Main_Function----------------------------###
###########################################################################
if __name__ == "__main__":
    args = len(sys.argv)
    if args != 2:
        raise ValueError(
            "INCORRECT NUMBER OF ARGS\nUsage: python3 parser.py <header file path>"
        )

    with open(sys.argv[1], "rb") as file:
        header_source = file.read()

    C_LANGUAGE = tree_sitter.Language(tree_sitter_c.language())
    parser = tree_sitter.Parser(C_LANGUAGE)
    tree = parser.parse(header_source)
    yaml = parse_translation_unit(tree.root_node)
    print(dump(yaml, sort_keys=False, explicit_start=True).strip())
    # print(str(tree.root_node))
