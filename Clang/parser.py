import clang.cindex
import yaml
import sys
from collections import defaultdict
import copy



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


def parse_type_decl(t):
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
        case type_name if type_name in list(THAPI_types.keys()) + [clang.cindex.TypeKind.POINTER]:
            return t.to_THAPI_decl()
        case clang.cindex.TypeKind.INCOMPLETEARRAY:
            if t.element_type.kind in [clang.cindex.TypeKind.INCOMPLETEARRAY, clang.cindex.TypeKind.CONSTANTARRAY]:
                return {
                    "kind": "array",
                    "type": parse_type_decl(t.element_type),
                }
            else:
                return {"kind": "array"}
        case clang.cindex.TypeKind.CONSTANTARRAY:
            if t.element_type.kind in [clang.cindex.TypeKind.INCOMPLETEARRAY, clang.cindex.TypeKind.CONSTANTARRAY]:
                return {
                    "kind": "array",
                    "type": parse_type_decl(t.element_type),
                    "length": parse_val(t.element_count),
                }
            else:
                return {
                    "kind": "array",
                    "length": parse_val(t.element_count)
                }
        case _:
            raise NotImplementedError(f"parse_type: #{k}\nfile: {t.translation_unit.spelling}")



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
                case _:
                    raise NotImplementedError(f"parse_type_ELABORATED: #{ke}")
        case type_name if type_name in list(THAPI_types.keys()) + [clang.cindex.TypeKind.POINTER]:
            return t.to_THAPI_param()
        case clang.cindex.TypeKind.INCOMPLETEARRAY:
            return {"kind": "array",
                    "type": parse_type_param(t.element_type)}
        case clang.cindex.TypeKind.CONSTANTARRAY:
            return{
                "kind": "array",
                "type": parse_type_param(t.element_type),
                "length": parse_val(t.element_count)}
        case _:
            raise NotImplementedError(f"parse_type: #{k}\nfile: {t.translation_unit.spelling}")


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
        "declarators": [{"kind": "declarator"}
                        | parse_pointer(type_node, "typedef")
                        | {"name": t.spelling}],
    }


def parse_function_decl(t):
    type_node = t.type.get_result()
    return {
        "kind": "declaration",
        "type": parse_type_decl(type_node),
        "declarators": [
            {
                "kind": "declarator",
                "indirect_type": {"kind": "function"}
                | parse_pointer(type_node, "func")
                | (
                    {"params": [parse_parameter(a) for a in t.get_arguments()]}
                    if [parse_parameter(a) for a in t.get_arguments()]
                    else {}
                ),
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
        case clang.cindex.TypeKind.INCOMPLETEARRAY | clang.cindex.TypeKind.CONSTANTARRAY:
            type_node = t.type
            while type_node.element_type.kind in [clang.cindex.TypeKind.INCOMPLETEARRAY, clang.cindex.TypeKind.CONSTANTARRAY]:
                type_node = type_node.element_type
            return {
                "kind": "declaration",
                "type": parse_type_decl(type_node.element_type),
                "declarators": [{"kind": "declarator",
                                 "indirect_type": parse_type_decl(t.type),
                                 "name": t.spelling}]
            }
        case _:
            return {
                "kind": "declaration",
                "type": parse_type_decl(t.type),
                "declarators": [{"kind": "declarator"}
                                | parse_pointer(t.type, "struct")
                                | {"name": t.spelling}],
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


def parse_val(v):
    if v < 0:
        return {
            "kind": "negative",
            "expr": {
                "kind": "int_literal",
                "val": abs(v),
            },
        }
    else:
        return{
            "kind": "int_literal",
            "val": v,
        }

def parse_enum(t):
    return {
        "kind": "enumerator",
        "name": t.spelling,
        "val": parse_val(t.enum_value),
    }


def parse_enum_decl(t):
    return {
        "kind": "declaration",
        "type": {
            "kind": "enum",
            "name": t.spelling,
            "members": [parse_enum(a) for a in t.get_children()],
        },
    }


if __name__ == "__main__": 
    t = clang.cindex.Index.create().parse(sys.argv[1], args=sys.argv[2:]).cursor
    # for w in t.diagnostics:
    #     print(f"WARNING: {w}")
    d = parse_translation_unit(t)
    # Prevent yaml dumper from using anchors and aliases for repeated data in the yaml
    # Done by monkey patching the ignore_aliases() function to always return True
    yaml.Dumper.ignore_aliases = lambda *args: True
    print(
        yaml.dump(
            d, sort_keys=False, explicit_start=True, default_flow_style=False,
        ).strip()
    )


"""TODO LIST
1. Multi-dimensional Arrays
"""