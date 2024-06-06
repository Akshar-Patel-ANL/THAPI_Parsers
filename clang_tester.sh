#!/bin/bash -e

for header in ./unit_tests/*.h; do
    echo $header
    ruby emit_yaml.rb $header > ruby.out
    python3 Clang/parser.py $header > ts.out
    diff ruby.out ts.out
done

