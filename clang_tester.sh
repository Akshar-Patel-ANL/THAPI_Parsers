#!/bin/bash
ret=0
for header in ./unit_tests/*.h; do
    echo $header
    ruby emit_yaml.rb $header > ruby.out
    python3 Clang/parser.py $header > ts.out
    if ! diff ruby.out ts.out
    then
    ((ret += 2))
    fi
done
echo number of cases failed:
echo $ret

