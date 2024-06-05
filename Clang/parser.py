import clang.cindex
import yaml
import sys
from collections import defaultdict


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


def parse_type(t):
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
        case (
            clang.cindex.TypeKind.INT
            | clang.cindex.TypeKind.CHAR_S
            | clang.cindex.TypeKind.DOUBLE
        ):
            return {"kind": str(k)}
        case _:
            raise NotImplementedError(f"parse_type: #{k}")


def parse_parameter(t):
    return {"kind": "parameter", "type": parse_type(t.type), "name": t.spelling}


def parse_typedef_decl(t):
    return {
        "kind": "declaration",
        "storage": ":typedef",
        "type": parse_type(t.underlying_typedef_type),
        "declarators": [{"kind": "declarator", "name": t.spelling}],
    }


def parse_function_decl(t):
    return {
        "kind": "declaration",
        "type": {"kind": str(t.type.get_result().kind)},
        "declarators": [
            {
                "kind": "declarator",
                "indirect_type": {
                    "kind": "function",
                    "params": [parse_parameter(a) for a in t.get_arguments()],
                },
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
    print(yaml.dump(d, sort_keys=False))
