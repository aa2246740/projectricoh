#!/bin/sh
if [ "$1" = "-c" ] && [ "$2" = "uv run --frozen lint-imports" ]; then
exec uv run --frozen lint-imports --cache-dir /Volumes/Workspace/Scratch/tmp/projectricoh/studio-g152-r1/fix/import-linter
fi
exec /bin/sh "$@"
