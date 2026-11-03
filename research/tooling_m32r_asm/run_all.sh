#!/bin/sh
set -eu

tool_root=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
project_root=$(CDPATH= cd -- "$tool_root/../.." && pwd)
source_dir="$project_root/research/tooling_m32r/src/binutils-2.43"
archive="$project_root/research/tooling_m32r/downloads/binutils-2.43.tar.xz"
build_dir="$tool_root/build"
prefix_dir="$tool_root/prefix"
evidence_dir="$tool_root/evidence"
expected_sha256=b53606f443ac8f01d1d5fc9c39497f2af322d99e14cea5c0b4b124d630379365

mkdir -p "$build_dir" "$prefix_dir/bin" "$evidence_dir"
test -f "$source_dir/configure"
test -f "$archive"
actual_sha256=$(shasum -a 256 "$archive" | awk '{print $1}')
if [ "$actual_sha256" != "$expected_sha256" ]; then
  echo "Binutils archive SHA-256 mismatch: $actual_sha256" >&2
  exit 1
fi

if [ ! -f "$build_dir/Makefile" ]; then
  (
    cd "$build_dir"
    "$source_dir/configure" \
      --target=m32r-elf \
      --prefix="$prefix_dir" \
      --disable-nls \
      --disable-werror \
      --disable-gdb \
      --disable-gdbserver \
      --disable-gold \
      --disable-gprof \
      --disable-gprofng \
      --disable-sim \
      --disable-libctf \
      --disable-shared \
      --enable-static \
      --without-zstd \
      --with-system-zlib
  ) > "$evidence_dir/configure.log" 2>&1
fi

make -C "$build_dir" -j8 MAKEINFO=true all-libiberty all-bfd all-opcodes \
  > "$evidence_dir/build-libraries.log" 2>&1
make -C "$build_dir" MAKEINFO=true configure-binutils configure-gas configure-ld \
  > "$evidence_dir/configure-tools.log" 2>&1
make -C "$build_dir/binutils" -j8 MAKEINFO=true objcopy \
  > "$evidence_dir/build-objcopy.log" 2>&1
make -C "$build_dir/gas" -j8 MAKEINFO=true all \
  > "$evidence_dir/build-gas.log" 2>&1
make -C "$build_dir/ld" -j8 MAKEINFO=true all \
  > "$evidence_dir/build-ld.log" 2>&1

cp "$build_dir/gas/as-new" "$prefix_dir/bin/m32r-elf-as"
cp "$build_dir/ld/ld-new" "$prefix_dir/bin/m32r-elf-ld"
cp "$build_dir/binutils/objcopy" "$prefix_dir/bin/m32r-elf-objcopy"
chmod 755 \
  "$prefix_dir/bin/m32r-elf-as" \
  "$prefix_dir/bin/m32r-elf-ld" \
  "$prefix_dir/bin/m32r-elf-objcopy"

(
  cd "$project_root"
  python3 research/tooling_m32r_asm/verify_toolchain.py
)
