/* Lossless sequential JPEG encoder, predictor 1, Pt=0, 1x1 components.
   Input is little-endian uint16, row-major, components interleaved.
   Huffman category 0 has code 0; 1..15 use 10000..11110; 16 uses 111110.
   No all-one codeword, no restart intervals, entropy FF bytes are stuffed. */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

static FILE *out;
static uint64_t acc;
static unsigned bits;

static void fail(const char *s) { fprintf(stderr, "sof3: %s\n", s); exit(1); }
static unsigned number(const char *s, unsigned lo, unsigned hi) {
    char *end;
    unsigned long x = strtoul(s, &end, 10);
    if (!*s || *end || x < lo || x > hi) fail("argument out of range");
    return (unsigned)x;
}
static void byte(unsigned b) { if (fputc((int)b, out) == EOF) fail("write"); }
static void word(unsigned w) { byte(w >> 8); byte(w & 255); }
static void marker(unsigned m, unsigned n) { byte(255); byte(m); word(n); }
static void put(unsigned v, unsigned n) {
    acc = (acc << n) | v;
    bits += n;
    while (bits >= 8) {
        bits -= 8;
        unsigned b = (unsigned)((acc >> bits) & 255);
        byte(b);
        if (b == 255) byte(0);
    }
    acc &= bits ? ((UINT64_C(1) << bits) - 1) : 0;
}

int main(int argc, char **argv) {
    if (argc != 9) fail("usage: sof3 raw.u16 output.ljpg width height components precision id0 id1");
    unsigned w = number(argv[3], 1, 65535), h = number(argv[4], 1, 65535);
    unsigned c = number(argv[5], 1, 2), p = number(argv[6], 2, 16);
    unsigned ids[2] = {number(argv[7], 0, 255), number(argv[8], 0, 255)};
    if (c == 2 && ids[0] == ids[1]) fail("duplicate component IDs");
    FILE *in = fopen(argv[1], "rb");
    if (!in) fail("open input");
    size_t n = (size_t)w * h * c;
    if (n > SIZE_MAX / sizeof(uint16_t)) fail("size overflow");
    uint16_t *raw = malloc(n * sizeof *raw);
    if (!raw) fail("allocation");
    for (size_t i = 0; i < n; i++) {
        int a = fgetc(in), b = fgetc(in);
        if (a == EOF || b == EOF) fail("truncated input");
        unsigned v = (unsigned)a | ((unsigned)b << 8);
        if (v >= (1u << p)) fail("sample exceeds precision");
        raw[i] = (uint16_t)v;
    }
    if (fgetc(in) != EOF) fail("extra input");
    fclose(in);
    out = fopen(argv[2], "wb");
    if (!out) fail("open output");
    byte(255); byte(0xd8);
    marker(0xc3, 8 + 3 * c); byte(p); word(h); word(w); byte(c);
    for (unsigned k = 0; k < c; k++) { byte(ids[k]); byte(0x11); byte(0); }
    marker(0xc4, 2 + 1 + 16 + 17); byte(0);
    for (unsigned k = 1; k <= 16; k++) byte(k == 1 ? 1 : k == 5 ? 15 : k == 6 ? 1 : 0);
    for (unsigned k = 0; k <= 16; k++) byte(k);
    marker(0xda, 6 + 2 * c); byte(c);
    for (unsigned k = 0; k < c; k++) { byte(ids[k]); byte(0); }
    byte(1); byte(0); byte(0);
    for (unsigned y = 0; y < h; y++) for (unsigned x = 0; x < w; x++) {
        for (unsigned k = 0; k < c; k++) {
            size_t i = ((size_t)y * w + x) * c + k;
            int pred = y == 0 && x == 0 ? 1 << (p - 1) : x ? raw[i - c] : raw[i - (size_t)w * c];
            int d = raw[i] - pred;
            if (p == 16) { if (d > 32767) d -= 65536; if (d < -32768) d += 65536; }
            unsigned cat = 0, magnitude = (unsigned)(d < 0 ? -d : d);
            for (unsigned z = magnitude; z; z >>= 1) cat++;
            if (d == -32768) cat = 16;
            if (!cat) put(0, 1);
            else if (cat == 16) put(62, 6);
            else put(cat + 15, 5);
            if (cat && cat != 16) put(d >= 0 ? (unsigned)d : (unsigned)(d + (1 << cat) - 1), cat);
        }
    }
    if (bits) put((1u << (8 - bits)) - 1, 8 - bits);
    byte(255); byte(0xd9);
    if (fclose(out)) fail("close output");
    free(raw);
    return 0;
}
