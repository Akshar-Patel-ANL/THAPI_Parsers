#!/bin/bash
ret=0
for header in ./unit_tests/*.h; do
    echo $header
    name=$(basename $header .h)
    outpath="./unit_tests/ruby_out/$name.out"
    if test -f $outpath; then
        python3 Clang/parser.py $header > clang.out
        if ! diff $outpath clang.out
        then
        ((ret += 1))
        fi
    else
        ruby emit_yaml.rb $header > ruby.out
        python3 Clang/parser.py $header > clang.out
        if ! diff ruby.out clang.out
        then
        ((ret += 1))
        fi
    fi
done
echo number of cases failed:
echo $ret
exit $ret
