#!/usr/bin/env bash
echo "isort"
python3 -m isort --recursive ./src/
echo "autoflake"
python3 -m autoflake \
	--recursive \
	--in-place \
	--remove-unused-variables \
	--remove-all-unused-imports \
	./src/
echo "black"
python3 -m black ./src/
echo "yaml_format"
./yaml_format.sh ./src/
