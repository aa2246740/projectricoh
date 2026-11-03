#!/bin/sh
set -eu

tool_root=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
project_root=$(CDPATH= cd -- "$tool_root/../.." && pwd)
archive="$tool_root/downloads/binutils-2.43.tar.xz"
source_dir="$tool_root/src/binutils-2.43"
build_dir="$tool_root/build-macos"
prefix_dir="$tool_root/prefix"
expected_sha256=b53606f443ac8f01d1d5fc9c39497f2af322d99e14cea5c0b4b124d630379365
source_url=https://ftp.gnu.org/gnu/binutils/binutils-2.43.tar.xz

mkdir -p "$tool_root/downloads" "$tool_root/src" "$build_dir" "$prefix_dir/bin" "$tool_root/evidence"

if [ ! -f "$archive" ]; then
  curl -fL --proto '=https' --tlsv1.2 -o "$archive" "$source_url"
fi
actual_sha256=$(shasum -a 256 "$archive" | awk '{print $1}')
if [ "$actual_sha256" != "$expected_sha256" ]; then
  echo "Binutils archive SHA-256 mismatch: $actual_sha256" >&2
  exit 1
fi

if [ ! -f "$source_dir/configure" ]; then
  tar -xJf "$archive" -C "$tool_root/src"
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
      --disable-gas \
      --disable-ld \
      --disable-gold \
      --disable-gprof \
      --disable-gprofng \
      --disable-sim \
      --disable-libctf \
      --disable-shared \
      --enable-static \
      --without-zstd \
      --with-system-zlib
  ) > "$tool_root/evidence/configure-macos.log" 2>&1
fi

make -C "$build_dir" -j8 MAKEINFO=true all-libiberty all-bfd all-opcodes \
  > "$tool_root/evidence/build-libraries-macos.log" 2>&1
make -C "$build_dir" MAKEINFO=true configure-binutils \
  > "$tool_root/evidence/configure-binutils.log" 2>&1
make -C "$build_dir/binutils" -j8 MAKEINFO=true objdump \
  > "$tool_root/evidence/build-objdump.log" 2>&1
cp "$build_dir/binutils/objdump" "$prefix_dir/bin/m32r-elf-objdump"
chmod 755 "$prefix_dir/bin/m32r-elf-objdump"

(
  cd "$project_root"
  python3 research/tooling_m32r/analyze_segments.py
)
