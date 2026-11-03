#!/bin/sh
set -eu

tool_root=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
project_root=$(CDPATH= cd -- "$tool_root/../.." && pwd)
download_dir="$tool_root/downloads"
source_dir="$tool_root/src"
build_dir="$tool_root/build"
prefix_dir="$tool_root/prefix"
deps_prefix="$prefix_dir/deps"
gcc_prefix="$prefix_dir/gcc"
evidence_dir="$tool_root/evidence"
binutils_dir="$project_root/research/tooling_m32r_asm/prefix/bin"
gmp_prefix=/opt/homebrew/opt/gmp

gcc_archive="$download_dir/gcc-13.4.0.tar.xz"
mpfr_archive="$download_dir/mpfr-4.1.0.tar.bz2"
mpc_archive="$download_dir/mpc-1.2.1.tar.gz"
gcc_sha512=9b4b83ecf51ef355b868608b8d257b2fa435c06d2719cb86657a7c2c2a0828ff4ce04e9bac1055bbcad8ed5b4da524cafaef654785e23a50233d95d89201e35f
mpfr_sha512=410208ee0d48474c1c10d3d4a59decd2dfa187064183b09358ec4c4666e34d74383128436b404123b831e585d81a9176b24c7ced9d913967c5fce35d4040a0b4
mpc_sha512=3279f813ab37f47fdcc800e4ac5f306417d07f539593ca715876e43e04896e1d5bceccfb288ef2908a3f24b760747d0dbd0392a24b9b341bc3e12082e5c836ee

mkdir -p "$build_dir/mpfr" "$build_dir/mpc" "$build_dir/gcc" "$deps_prefix" "$gcc_prefix" "$evidence_dir"
test -x "$binutils_dir/m32r-elf-as"
test -x "$binutils_dir/m32r-elf-ld"
test -d "$gmp_prefix/include"
test -d "$gmp_prefix/lib"

verify_sha512() {
  archive=$1
  expected=$2
  actual=$(shasum -a 512 "$archive" | awk '{print $1}')
  if [ "$actual" != "$expected" ]; then
    echo "SHA-512 mismatch for $archive: $actual" >&2
    exit 1
  fi
}

verify_sha512 "$gcc_archive" "$gcc_sha512"
verify_sha512 "$mpfr_archive" "$mpfr_sha512"
verify_sha512 "$mpc_archive" "$mpc_sha512"

if [ ! -f "$source_dir/gcc-13.4.0/configure" ]; then
  tar -xJf "$gcc_archive" -C "$source_dir"
fi
if [ ! -f "$source_dir/mpfr-4.1.0/configure" ]; then
  tar -xjf "$mpfr_archive" -C "$source_dir"
fi
if [ ! -f "$source_dir/mpc-1.2.1/configure" ]; then
  tar -xzf "$mpc_archive" -C "$source_dir"
fi

if [ ! -f "$build_dir/mpfr/Makefile" ]; then
  (
    cd "$build_dir/mpfr"
    "$source_dir/mpfr-4.1.0/configure" \
      --prefix="$deps_prefix" \
      --with-gmp="$gmp_prefix" \
      --disable-shared \
      --enable-static
  ) > "$evidence_dir/configure-mpfr.log" 2>&1
fi
if [ ! -f "$deps_prefix/lib/libmpfr.a" ]; then
  make -C "$build_dir/mpfr" -j8 > "$evidence_dir/build-mpfr.log" 2>&1
  make -C "$build_dir/mpfr" install > "$evidence_dir/install-mpfr.log" 2>&1
fi

if [ ! -f "$build_dir/mpc/Makefile" ]; then
  (
    cd "$build_dir/mpc"
    "$source_dir/mpc-1.2.1/configure" \
      --prefix="$deps_prefix" \
      --with-gmp="$gmp_prefix" \
      --with-mpfr="$deps_prefix" \
      --disable-shared \
      --enable-static
  ) > "$evidence_dir/configure-mpc.log" 2>&1
fi
if [ ! -f "$deps_prefix/lib/libmpc.a" ]; then
  make -C "$build_dir/mpc" -j8 > "$evidence_dir/build-mpc.log" 2>&1
  make -C "$build_dir/mpc" install > "$evidence_dir/install-mpc.log" 2>&1
fi

if [ ! -f "$build_dir/gcc/Makefile" ]; then
  (
    cd "$build_dir/gcc"
    PATH="$binutils_dir:$PATH" "$source_dir/gcc-13.4.0/configure" \
      --target=m32r-elf \
      --prefix="$gcc_prefix" \
      --enable-languages=c \
      --disable-bootstrap \
      --disable-multilib \
      --without-headers \
      --disable-nls \
      --disable-werror \
      --disable-shared \
      --disable-threads \
      --disable-libatomic \
      --disable-libgomp \
      --disable-libquadmath \
      --disable-libsanitizer \
      --disable-libssp \
      --disable-libstdcxx \
      --with-system-zlib \
      --with-gmp="$gmp_prefix" \
      --with-mpfr="$deps_prefix" \
      --with-mpc="$deps_prefix" \
      --with-as="$binutils_dir/m32r-elf-as" \
      --with-ld="$binutils_dir/m32r-elf-ld"
  ) > "$evidence_dir/configure-gcc.log" 2>&1
fi

if [ ! -x "$gcc_prefix/bin/m32r-elf-gcc" ]; then
  PATH="$binutils_dir:$PATH" make -C "$build_dir/gcc" -j8 MAKEINFO=true all-gcc \
    > "$evidence_dir/build-gcc.log" 2>&1
  PATH="$binutils_dir:$PATH" make -C "$build_dir/gcc" MAKEINFO=true install-gcc \
    > "$evidence_dir/install-gcc.log" 2>&1
fi

(
  cd "$project_root"
  python3 research/tooling_m32r_c/verify_compiler.py
)
