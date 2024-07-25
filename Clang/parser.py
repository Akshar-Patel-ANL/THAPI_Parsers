import clang.cindex
import yaml
import sys
from collections import defaultdict
import re

clang.cindex.Config.set_library_file("/usr/lib/x86_64-linux-gnu/libclang-17.so.1")

THAPI_types = {
    clang.cindex.TypeKind.VOID: {"kind": "void"},
    clang.cindex.TypeKind.FLOAT: {"kind": "float"},
    clang.cindex.TypeKind.DOUBLE: {"kind": "float", "longness": 1},
    clang.cindex.TypeKind.LONGDOUBLE: {"kind": "float", "longness": 2},
    clang.cindex.TypeKind.INT: {"kind": "int"},
    clang.cindex.TypeKind.UINT: {"kind": "int", "unsigned": True},
    clang.cindex.TypeKind.SHORT: {"kind": "int", "longness": -1},
    clang.cindex.TypeKind.USHORT: {"kind": "int", "longness": -1, "unsigned": True},
    clang.cindex.TypeKind.LONG: {"kind": "int", "longness": 1},
    clang.cindex.TypeKind.ULONG: {"kind": "int", "longness": 1, "unsigned": True},
    clang.cindex.TypeKind.LONGLONG: {"kind": "int", "longness": 2},
    clang.cindex.TypeKind.ULONGLONG: {"kind": "int", "longness": 2, "unsigned": True},
    clang.cindex.TypeKind.CHAR_U: {"kind": "char"},
    clang.cindex.TypeKind.UCHAR: {"kind": "char"},
    clang.cindex.TypeKind.CHAR_S: {"kind": "char"},
    clang.cindex.TypeKind.SCHAR: {"kind": "char", "signed": True},
}


def to_THAPI_param(self):
    if self.kind == clang.cindex.TypeKind.POINTER:
        return {"kind": "pointer", "type": to_THAPI_param(self.get_pointee())}
    return THAPI_types[self.kind]


clang.cindex.Type.to_THAPI_param = to_THAPI_param


def to_THAPI_decl(self):
    if self.kind == clang.cindex.TypeKind.POINTER:
        return to_THAPI_decl(self.get_pointee())
    return THAPI_types[self.kind]


clang.cindex.Type.to_THAPI_decl = to_THAPI_decl


def match_typedef(target_node, potential_typedef_node):
    A = potential_typedef_node.kind == clang.cindex.CursorKind.TYPEDEF_DECL
    B = (
        target_node.spelling
        == potential_typedef_node.underlying_typedef_type.get_declaration().spelling
    )
    return A and B


def merge_typedef(target, typedef):
    return {
        "kind": "declaration",
        "storage": ":typedef",
        "type": target["type"],
        "declarators": typedef["declarators"],
    }


def extract_match(c):
    return next(
        (parse_typedef_decl(c2) for c2 in t.get_children() if match_typedef(c, c2)),
        None,
    )


def parse_translation_unit(t):
    # d_entities = defaultdict(list)
    entities = []
    for c in t.get_children():
        if c.location.is_in_system_header:
            continue
        # entities = d_entities[str(c.location.file)]
        match k := c.kind:
            case clang.cindex.CursorKind.FUNCTION_DECL:
                entities.append(parse_function_decl(c))
            case clang.cindex.CursorKind.TYPEDEF_DECL:
                if c.underlying_typedef_type.get_declaration().kind not in [
                    clang.cindex.CursorKind.STRUCT_DECL,
                    clang.cindex.CursorKind.ENUM_DECL,
                    clang.cindex.CursorKind.UNION_DECL,
                ]:
                    entities.append(parse_typedef_decl(c))
            case clang.cindex.CursorKind.STRUCT_DECL:
                dict_struct = parse_struct_decl(c)
                # Check if the struct is typedef. If yes, need to modify the dict
                dict_typedef = extract_match(c)
                if dict_typedef:
                    dict_struct = merge_typedef(dict_struct, dict_typedef)
                entities.append(dict_struct)
            case clang.cindex.CursorKind.ENUM_DECL:
                dict_enum = parse_enum_decl(c)
                # Check if the enum is typedef. If yes, need to modify the dict
                dict_typedef = extract_match(c)
                if dict_typedef:
                    dict_enum = merge_typedef(dict_enum, dict_typedef)
                entities.append(dict_enum)
            case clang.cindex.CursorKind.UNION_DECL:
                dict_union = parse_union_decl(c)
                # Check if the enum is typedef. If yes, need to modify the dict
                dict_typedef = extract_match(c)
                if dict_typedef:
                    dict_union = merge_typedef(dict_union, dict_typedef)
                entities.append(dict_union)
            case _:
                raise NotImplementedError(f"parse_translation_unit: #{k}")
    return {"kind": "translation_unit", "entities": entities}
    # return {"kind": "translation_unit", "entities": dict(d_entities)}


def parse_type_decl(t):
    match k := t.kind:
        case clang.cindex.TypeKind.ELABORATED:
            d = t.get_declaration()
            match ke := d.kind:
                case clang.cindex.CursorKind.TYPEDEF_DECL:
                    return {"kind": "custom_type", "name": d.spelling}
                case clang.cindex.CursorKind.STRUCT_DECL:
                    return parse_struct_decl(d)["type"]
                case clang.cindex.CursorKind.ENUM_DECL:
                    return parse_enum_decl(d)["type"]
                case clang.cindex.CursorKind.UNION_DECL:
                    return parse_union_decl(d)["type"]
                case _:
                    raise NotImplementedError(f"parse_type_ELABORATED: #{ke}")
        case type_name if type_name in list(THAPI_types.keys()) + [
            clang.cindex.TypeKind.POINTER
        ]:
            return t.to_THAPI_decl()
        case clang.cindex.TypeKind.INCOMPLETEARRAY:
            if t.element_type.kind in [
                clang.cindex.TypeKind.INCOMPLETEARRAY,
                clang.cindex.TypeKind.CONSTANTARRAY,
            ]:
                return {
                    "kind": "array",
                    "type": parse_type_decl(t.element_type),
                }
            else:
                return {"kind": "array"}
        case clang.cindex.TypeKind.CONSTANTARRAY:
            if t.element_type.kind in [
                clang.cindex.TypeKind.INCOMPLETEARRAY,
                clang.cindex.TypeKind.CONSTANTARRAY,
            ]:
                return {
                    "kind": "array",
                    "type": parse_type_decl(t.element_type),
                    "length": parse_val(t.element_count),
                }
            else:
                return {"kind": "array", "length": parse_val(t.element_count)}
        case _:
            raise NotImplementedError(
                f"parse_type: #{k}\nfile: {t.translation_unit.spelling}"
            )


def parse_type_param(t):
    match k := t.kind:
        case clang.cindex.TypeKind.ELABORATED:
            d = t.get_declaration()
            match ke := d.kind:
                case clang.cindex.CursorKind.TYPEDEF_DECL:
                    return {"kind": "custom_type", "name": d.spelling}
                case clang.cindex.CursorKind.STRUCT_DECL:
                    return {"kind": "struct", "name": d.spelling}
                case clang.cindex.CursorKind.ENUM_DECL:
                    return {"kind": "enum", "name": d.spelling}
                case clang.cindex.CursorKind.UNION_DECL:
                    return {"kind": "union", "name": d.spelling}
                case _:
                    raise NotImplementedError(f"parse_type_ELABORATED: #{ke}")
        case type_name if type_name in list(THAPI_types.keys()) + [
            clang.cindex.TypeKind.POINTER
        ]:
            return t.to_THAPI_param()
        case clang.cindex.TypeKind.INCOMPLETEARRAY:
            return {"kind": "array", "type": parse_type_param(t.element_type)}
        case clang.cindex.TypeKind.CONSTANTARRAY:
            return {
                "kind": "array",
                "type": parse_type_param(t.element_type),
                "length": parse_val(t.element_count),
            }
        case _:
            raise NotImplementedError(
                f"parse_type: #{k}\nfile: {t.translation_unit.spelling}"
            )


def parse_parameter(t):
    return {
        "kind": "parameter",
        "type": parse_type_param(t.type),
        "name": t.spelling,
    }


def parse_typedef_decl(t):
    type_node = t.underlying_typedef_type
    return {
        "kind": "declaration",
        "storage": ":typedef",
        "type": parse_type_decl(type_node),
        "declarators": [
            {"kind": "declarator"}
            | parse_pointer(type_node, "typedef")
            | {"name": t.spelling}
        ],
    }


def parse_function_decl(t):
    type_node = t.type.get_result()
    params_d = {}
    if params := [parse_parameter(a) for a in t.get_arguments()]:
        params_d = {"params": params}
    return {
        "kind": "declaration",
        "type": parse_type_decl(type_node),
        "declarators": [
            {
                "kind": "declarator",
                "indirect_type": {"kind": "function"}
                | parse_pointer(type_node, "func")
                | params_d,
                "name": t.spelling,
            },
        ],
    }


def parse_pointer(t, form):
    if t.kind == clang.cindex.TypeKind.POINTER:
        ptr_dict = {"kind": "pointer"}
        type_node = t.get_pointee()
        while type_node.kind == clang.cindex.TypeKind.POINTER:
            ptr_dict = {"kind": "pointer", "type": ptr_dict}
            type_node = type_node.get_pointee()
        match form:
            case "func":
                return {"type": ptr_dict}
            case "typedef" | "struct" | "enum":
                return {"indirect_type": ptr_dict}
            case _:
                raise NotImplementedError(f"parse_pointer form: #{form}")
    else:
        return {}


def parse_field(t):
    match k := t.type.kind:
        case (
            clang.cindex.TypeKind.INCOMPLETEARRAY | clang.cindex.TypeKind.CONSTANTARRAY
        ):
            type_node = t.type
            while type_node.element_type.kind in [
                clang.cindex.TypeKind.INCOMPLETEARRAY,
                clang.cindex.TypeKind.CONSTANTARRAY,
            ]:
                type_node = type_node.element_type
            return {
                "kind": "declaration",
                "type": parse_type_decl(type_node.element_type),
                "declarators": [
                    {
                        "kind": "declarator",
                        "indirect_type": parse_type_decl(t.type),
                        "name": t.spelling,
                    }
                ],
            }
        case _:
            return {
                "kind": "declaration",
                "type": parse_type_decl(t.type),
                "declarators": [
                    {"kind": "declarator"}
                    | parse_pointer(t.type, "struct")
                    | {"name": t.spelling}
                ],
            }


def extract_name(t):
    if not re.search(r"\(unnamed at ", t.spelling):
        return t.spelling
    return None


def parse_struct_decl(t):
    members_d = {}
    if members := [parse_field(a) for a in t.type.get_fields()]:
        members_d = {"members": members}
    name_d = {}
    if name := extract_name(t):
        name_d = {"name": name}
    return {
        "kind": "declaration",
        "type": {"kind": "struct"} | name_d | members_d,
    }


def parse_val(v, hex=False):
    hex_dict = {}
    if hex:
        hex_dict = {"format": ":hex"}
    if v < 0:
        return {
            "kind": "negative",
            "expr": {"kind": "int_literal"} | hex_dict | {"val": abs(v)},
        }
    else:
        return {"kind": "int_literal"} | hex_dict | {"val": v}


def is_hex(t):
    with open(t.location.file.name, "r") as f:
        source = f.readlines()  
    return re.search(r"=[\s+-]*0x", source[t.location.line - 1], re.IGNORECASE)

def parse_enum(t):
    return {
        "kind": "enumerator",
        "name": t.spelling,
        "val": parse_val(t.enum_value, is_hex(t)),
    }


def parse_enum_decl(t):
    name_d = {}
    if name := extract_name(t):
        name_d = {"name": name}
    return {
        "kind": "declaration",
        "type": {"kind": "enum"}
        | name_d
        | {"members": [parse_enum(a) for a in t.get_children()]},
    }


def parse_union_decl(t):
    members_d = {}
    if members := [parse_field(a) for a in t.type.get_fields()]:
        members_d = {"members": members}
    name_d = {}
    if name := extract_name(t):
        name_d = {"name": name}
    return {
        "kind": "declaration",
        "type": {"kind": "union"} | name_d | members_d,
    }


if __name__ == "__main__":
    f = open(sys.argv[1])
    source = f.readlines()

    t = clang.cindex.Index.create().parse(sys.argv[1], args=sys.argv[2:]).cursor
    # for w in t.diagnostics:
    #     print(f"WARNING: {w}")
    d = parse_translation_unit(t)
    # Prevent yaml dumper from using anchors and aliases for repeated data in the yaml
    # Done by monkey patching the ignore_aliases() function to always return True
    yaml.Dumper.ignore_aliases = lambda *args: True
    print(
        yaml.dump(
            d,
            sort_keys=False,
            explicit_start=True,
            default_flow_style=False,
        ).strip()
    )


"""TODO LIST
1. Multi-dimensional Arrays
"""
