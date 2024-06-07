import clang.cindex
import yaml
import sys
from collections import defaultdict

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
    k = self.kind
    if k == clang.cindex.TypeKind.POINTER:
        return {"kind": "pointer", "type": to_THAPI_param(self.get_pointee())}
    return THAPI_types[k]


clang.cindex.Type.to_THAPI_param = to_THAPI_param


def to_THAPI_decl(self):
    return THAPI_types[self.kind]


clang.cindex.Type.to_THAPI_decl = to_THAPI_decl


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
                entities.append(parse_typedef_decl(c))
            case clang.cindex.CursorKind.STRUCT_DECL:
                entities.append(parse_struct_decl(c))
            case clang.cindex.CursorKind.ENUM_DECL:
                entities.append(parse_enum_decl(c))
            case _:
                raise NotImplementedError(f"parse_translation_unit: #{k}")
    return {"kind": "translation_unit", "entities": entities}
    # return {"kind": "translation_unit", "entities": dict(d_entities)}


def parse_type(t, form="decl"):
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
                case _:
                    raise NotImplementedError(f"parse_type_ELABORATED: #{ke}")
        case type if type in list(THAPI_types.keys()) + [clang.cindex.TypeKind.POINTER]:
            match form:
                case "decl":
                    return t.to_THAPI_decl()
                case "param":
                    return t.to_THAPI_param()
                case _:
                    raise NotImplementedError(
                        f"Missing parsing for for THAPI_types: #{form}"
                    )
        case _:
            raise NotImplementedError(f"parse_type: #{k}")


def parse_parameter(t):
    return {
        "kind": "parameter",
        "type": parse_type(t.type, "param"),
        "name": t.spelling,
    }


def parse_typedef_decl(t):
    type_node = t.underlying_typedef_type
    ptr_dict = {}
    if type_node.kind == clang.cindex.TypeKind.POINTER:
        ptr_dict = {"kind": "pointer"}
        type_node = type_node.get_pointee()
        while type_node.kind == clang.cindex.TypeKind.POINTER:
            ptr_dict = {"kind": "pointer", "type": ptr_dict}
            type_node = type_node.get_pointee()
        ptr_dict = {"indirect_type": ptr_dict}
    return {
        "kind": "declaration",
        "storage": ":typedef",
        "type": parse_type(type_node),
        "declarators": [{"kind": "declarator"} | ptr_dict | {"name": t.spelling}],
    }


def parse_function_decl(t):
    type_node = t.type.get_result()
    ptr_dict = {}
    while type_node.kind == clang.cindex.TypeKind.POINTER:
        ptr_dict = {"type": {"kind": "pointer"} | ptr_dict}
        type_node = type_node.get_pointee()
    return {
        "kind": "declaration",
        "type": parse_type(type_node),
        "declarators": [
            {
                "kind": "declarator",
                "indirect_type": {"kind": "function"}
                | ptr_dict
                | (
                    {"params": [parse_parameter(a) for a in t.get_arguments()]}
                    if [parse_parameter(a) for a in t.get_arguments()]
                    else {}
                ),
                "name": t.spelling,
            },
        ],
    }


def parse_field(t):
    return {
        "kind": "declaration",
        "type": parse_type(t.type),
        "declarators": [{"kind": "declarator", "name": t.spelling}],
    }


def parse_struct_decl(t):
    return {
        "kind": "declaration",
        "type": {
            "kind": "struct",
            "name": t.spelling,
            "members": [parse_field(a) for a in t.type.get_fields()],
        },
    }


def parse_enum(t, a):
    return {
        "kind": "enumerator",
        "name": t.spelling,
        "val": {"kind": str(a.kind), "val": t.enum_value},
    }


def parse_enum_decl(t):
    return {
        "kind": "declaration",
        "type": {
            "kind": "enum",
            "name": t.spelling,
            "members": [parse_enum(a, t.enum_type) for a in t.get_children()],
        },
    }


if __name__ == "__main__":
    t = clang.cindex.Index.create().parse(sys.argv[1]).cursor
    d = parse_translation_unit(t)
    yaml.Dumper.ignore_aliases = lambda *args: True
    print(
        yaml.dump(
            d, sort_keys=False, explicit_start=True, default_flow_style=False
        ).strip()
    )
