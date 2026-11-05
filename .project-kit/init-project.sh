#!/bin/sh
# Keep this launcher with init_project.py and the reusable kit.
set -eu
script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
exec python3 "$script_dir/init_project.py" "$@"
