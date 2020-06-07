#!/usr/bin/env bash

# Check options
check=0
exit_status=0
TEMPFILE="/tmp/yaml_format_temp.yml"

while [[ "$1" =~ ^- && ! "$1" == "--" ]]; do case $1 in
  -c | --check )
    check=1
    ;;
esac; shift; done
if [[ "$1" == '--' ]]; then shift; fi

# Get positional arg
dir=${1:-"./dags"}

files=$(find $dir -regex ".*\.yml")
for f in ${files[@]}; do
    if [[ $check -eq 1 ]]; then
        cp $f $TEMPFILE && \
        yamlfmt $TEMPFILE -w && \
        cmp --quiet $TEMPFILE $f
        
        if [[ $? -ne 0 ]]; then
            echo "$f not properly formatted."
            exit_status=1
        fi
        
    else
        yamlfmt $f -w || exit
    fi
done

if [[ $check -eq 1 ]] && [[ $exit_status -eq 0 ]]; then
    echo "Success! All yaml files properly formatted."
fi

exit $exit_status
