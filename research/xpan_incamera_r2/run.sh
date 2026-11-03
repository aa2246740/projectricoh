#!/bin/sh
set -eu
task_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
policy="(version 1)(allow default)(deny network*)(deny file-write*)(allow file-write* (subpath \"$task_dir\"))(allow file-write-data (literal \"/dev/null\"))"
exec /usr/bin/sandbox-exec -p "$policy" /usr/bin/python3 -I -B "$task_dir/offline.py" "$@"
