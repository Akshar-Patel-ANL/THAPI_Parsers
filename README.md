Toy parsers to be possibly used for THAPI``

# Possible Changes in YAML format

## Consistent handling of pointers

As of right now, pointers are handled and expressed in the yaml differently based off the different contexts of their declaration (as a parameter, as a function return type, and as a type defintion). 

Current differences between pointer and non-pointer types

### Parameters Example

#### void foo(int bar)
```yaml
- kind: declaration
  type:
    kind: void
  declarators:
  - kind: declarator
    indirect_type:
      kind: function
      params:
      - kind: parameter
        type:
          kind: int
        name: bar
    name: foo
```

#### void foo(int *bar);
```yaml
- kind: declaration
  type:
    kind: void
  declarators:
  - kind: declarator
    indirect_type:
      kind: function
      params:
      - kind: parameter
        type:
          kind: pointer
          type:
            kind: int
        name: bar
    name: foo
```

### Function Return Example

#### int foo();
```yaml
- kind: declaration
  type:
    kind: int
  declarators:
  - kind: declarator
    indirect_type:
      kind: function
    name: foo
```

### int* foo();
```yaml
- kind: declaration
  type:
    kind: int
  declarators:
  - kind: declarator
    indirect_type:
      kind: function
      type:
        kind: pointer
    name: foo
```

### Type Definition Example

#### typedef int foo;
```yaml
- kind: declaration
  storage: :typedef
  type:
    kind: int
  declarators:
  - kind: declarator
    name: foo
```

#### typedef int* foo;
```yaml
- kind: declaration
  storage: :typedef
  type:
    kind: int
  declarators:
  - kind: declarator
    indirect_type:
      kind: pointer
    name: foo
```

### Proposed Change

Change the function return and type definition styles to match that of the parameters, meaing that additional information denoting that a type is a pointer would only be where the other information for that type is, rather than placing it elsewhere in the yaml stucture. Example YAML files for the changed function return and type definition below

### int* foo();
```yaml
- kind: declaration
  type:
    kind: pointer
    type:
        kind: int
  declarators:
  - kind: declarator
    indirect_type:
      kind: function
    name: foo
```

#### typedef int* foo;
```yaml
- kind: declaration
  storage: :typedef
  type:
    kind: pointer
    type:
        kind: int
  declarators:
  - kind: declarator
    name: foo
```
## Integer literals

Whenever an interger literal is found in a file, the ruby parser differentiates it from variable integers, but the clang parser we are using conflates these literal integers with variable integers to all be the same type, making it annoying to differentiate the two when making the yaml.

### Example of ruby parser

#### enum foo {ONE = 1};
```yaml
kind: translation_unit
entities:
- kind: declaration
  type:
    kind: enum
    name: foo
    members:
    - kind: enumerator
      name: ONE
      val:
        kind: int_literal
        val: 1
```

Is it necessary to have `int_literal` rather than just `int`?