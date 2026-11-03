# GNU Binutils 2.43 source provenance

- Source URL: https://ftp.gnu.org/gnu/binutils/binutils-2.43.tar.xz
- GNU release announcement and published checksums: https://sourceware.org/pipermail/binutils/2024-August/136151.html
- Download date: 2026-10-12
- Archive size: 28,175,768 bytes
- SHA-256: `b53606f443ac8f01d1d5fc9c39497f2af322d99e14cea5c0b4b124d630379365`
- Local archive: `downloads/binutils-2.43.tar.xz`
- Source tree: `src/binutils-2.43/`

The SHA-256 matches the value in the GNU Binutils 2.43 release announcement. The archive contains `bfd/cpu-m32r.c`, `opcodes/m32r-dis.c`, `opcodes/m32r-opc.c`, and the official M32R gas tests used for the mixed-width decoding check.

The build runs official release code locally. It does not execute Ricoh firmware, use a network installer, change a global tool directory, or write agent configuration.
