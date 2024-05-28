#!/bin/bash

for header in ./unit_tests/*.h; do
    name=${header##.*}
    ruby emit_yaml.rb $header >> ruby.out
    python3 Tree_sitter/parser.py $header >> ts.out
    res= diff -q --suppress-common-lines --ignore-matching-lines="---" ruby.out ts.out
done

rm ruby.out
rm ts.out