#!/bin/sh
# Installed kit: default to this kit config from any working directory.
set -eu
script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
exec python3 "$script_dir/multi_git.py" --config "$script_dir/../multi-git.conf" "$@"
