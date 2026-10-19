#!/bin/sh
set -eu

SCRIPT_DIRECTORY=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PROJECT_ROOT=$(CDPATH= cd -- "$SCRIPT_DIRECTORY/../.." && pwd)
ARTIFACT_DIRECTORY="$PROJECT_ROOT/artifacts/recipe-core"
COMPILER=${CC:-clang}

mkdir -p "$ARTIFACT_DIRECTORY/host-files"
"$COMPILER" --version > "$ARTIFACT_DIRECTORY/toolchain.txt"

"$COMPILER" \
    -std=c11 \
    -ffreestanding \
    -fno-builtin \
    -fno-stack-protector \
    -Wall \
    -Wextra \
    -Werror \
    -Wconversion \
    -Wsign-conversion \
    -Wshadow \
    -Wstrict-prototypes \
    -Wmissing-prototypes \
    -pedantic \
    -c "$SCRIPT_DIRECTORY/recipe_core.c" \
    -o "$ARTIFACT_DIRECTORY/recipe_core.freestanding.o"

UNDEFINED_SYMBOLS=$(nm -u "$ARTIFACT_DIRECTORY/recipe_core.freestanding.o")
if [ -n "$UNDEFINED_SYMBOLS" ]; then
    printf '%s\n' "$UNDEFINED_SYMBOLS" >&2
    exit 1
fi

"$COMPILER" \
    -std=c11 \
    -Wall \
    -Wextra \
    -Werror \
    -Wconversion \
    -Wsign-conversion \
    -Wshadow \
    -Wstrict-prototypes \
    -Wmissing-prototypes \
    -pedantic \
    "$SCRIPT_DIRECTORY/recipe_core.c" \
    "$SCRIPT_DIRECTORY/tests/host_file_store.c" \
    "$SCRIPT_DIRECTORY/tests/test_recipe_core.c" \
    -o "$ARTIFACT_DIRECTORY/test_recipe_core"

HOST_OUTPUT=$("$ARTIFACT_DIRECTORY/test_recipe_core" "$ARTIFACT_DIRECTORY")

"$COMPILER" \
    -std=c11 \
    -Wall \
    -Wextra \
    -Werror \
    -Wconversion \
    -Wsign-conversion \
    -Wshadow \
    -Wstrict-prototypes \
    -Wmissing-prototypes \
    -pedantic \
    -fsanitize=address,undefined \
    -fno-omit-frame-pointer \
    "$SCRIPT_DIRECTORY/recipe_core.c" \
    "$SCRIPT_DIRECTORY/tests/host_file_store.c" \
    "$SCRIPT_DIRECTORY/tests/test_recipe_core.c" \
    -o "$ARTIFACT_DIRECTORY/test_recipe_core_sanitized"

SANITIZER_OUTPUT=$("$ARTIFACT_DIRECTORY/test_recipe_core_sanitized" "$ARTIFACT_DIRECTORY")

{
    printf 'freestanding: no undefined symbols\n'
    printf 'host: %s\n' "$HOST_OUTPUT"
    printf 'asan-ubsan: %s\n' "$SANITIZER_OUTPUT"
} > "$ARTIFACT_DIRECTORY/test-results.txt"

cat "$ARTIFACT_DIRECTORY/test-results.txt"
python3 "$SCRIPT_DIRECTORY/verify.py" "$ARTIFACT_DIRECTORY"
