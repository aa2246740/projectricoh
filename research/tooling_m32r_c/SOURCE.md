# GNU source provenance

The fixed compiler source is GNU GCC 13.4.0.

- Release announcement: https://gcc.gnu.org/pipermail/gcc-announce/2025/000187.html
- Source URL: https://gcc.gnu.org/pub/gcc/releases/gcc-13.4.0/gcc-13.4.0.tar.xz
- Official checksum file: https://gcc.gnu.org/pub/gcc/releases/gcc-13.4.0/sha512.sum
- Saved checksum file: `evidence/official-gcc-sha512.sum`
- Archive SHA-512: `9b4b83ecf51ef355b868608b8d257b2fa435c06d2719cb86657a7c2c2a0828ff4ce04e9bac1055bbcad8ed5b4da524cafaef654785e23a50233d95d89201e35f`

GCC 13.4.0 names MPFR 4.1.0 and MPC 1.2.1 in `contrib/download_prerequisites`. Their SHA-512 values come from the adjacent `contrib/prerequisites.sha512` file.

- MPFR URL: https://gcc.gnu.org/pub/gcc/infrastructure/mpfr-4.1.0.tar.bz2
- MPFR SHA-512: `410208ee0d48474c1c10d3d4a59decd2dfa187064183b09358ec4c4666e34d74383128436b404123b831e585d81a9176b24c7ced9d913967c5fce35d4040a0b4`
- MPC URL: https://gcc.gnu.org/pub/gcc/infrastructure/mpc-1.2.1.tar.gz
- MPC SHA-512: `3279f813ab37f47fdcc800e4ac5f306417d07f539593ca715876e43e04896e1d5bceccfb288ef2908a3f24b760747d0dbd0392a24b9b341bc3e12082e5c836ee`

The build uses the installed read-only GMP 6.3.0 at `/opt/homebrew/opt/gmp`. It builds MPFR and MPC inside this project. It does not run GCC's prerequisite download script.

The verified GCC source has a `m32r-*-elf*` target case in `gcc/config.gcc`. The same file lists `m32r-*-linux*` as unsupported. The Linux entry does not disable the ELF target.
