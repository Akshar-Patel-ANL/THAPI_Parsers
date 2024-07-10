#!/bin/bash
ret=0
for header in ./unit_tests/*.h; do
    echo $header
    ruby emit_yaml.rb $header > ruby.out
    python3 Clang/parser.py $header > clang.out
    if ! diff ruby.out clang.out
    then
    ((ret += 1))
    fi
done
echo number of cases failed:
echo $ret
exit $ret
