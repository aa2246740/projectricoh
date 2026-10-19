/* ITU-T T.81 lossless sequential JPEG (SOF3), predictor 1, point transform 0.
   One shared DC table, 1x1 sampling, no restart interval. Two components are
   interleaved one sample at a time. Prediction is per component: 2^(P-1) at
   the first sample, Ra along the first line, Rb at the start of later lines,
   and Ra elsewhere. */
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>

static void die(const char *message) {
    fprintf(stderr, "lj92: %s\n", message);
    exit(1);
}

static uint8_t lengths[16][65536];
static uint8_t symbols[16][65536];
static int have_table[16];

static void build_table(int ident, const uint8_t *counts, const uint8_t *syms) {
    if (ident < 0 || ident > 15) die("bad Huffman id");
    memset(lengths[ident], 0, sizeof lengths[ident]);
    int code = 0, seen = 0;
    for (int size = 1; size <= 16; size++) {
        for (int n = 0; n < counts[size - 1]; n++) {
            int start = code << (16 - size);
            int stop = (code + 1) << (16 - size);
            for (int i = start; i < stop; i++) {
                lengths[ident][i] = (uint8_t)size;
                symbols[ident][i] = syms[seen];
            }
            seen++;
            code++;
        }
        code <<= 1;
    }
    have_table[ident] = 1;
}

static uint8_t *unstuff(const uint8_t *scan, size_t n, size_t *out_n) {
    uint8_t *out = malloc(n + 4);
    if (!out) die("out of memory");
    size_t w = 0;
    for (size_t i = 0; i < n; i++) {
        if (scan[i] != 0xff) {
            out[w++] = scan[i];
            continue;
        }
        if (i + 1 >= n) break;
        uint8_t nxt = scan[++i];
        if (nxt == 0x00) {
            out[w++] = 0xff;
            continue;
        }
        if (nxt == 0xd9) break;
        die("unexpected marker in scan");
    }
    out[w] = out[w + 1] = out[w + 2] = out[w + 3] = 0;
    *out_n = w;
    return out;
}

int main(int argc, char **argv) {
    if (argc != 3) die("usage: lj92 input.jpg output.u16");
    FILE *in = fopen(argv[1], "rb");
    if (!in) die("cannot open input");
    fseek(in, 0, SEEK_END);
    long file_size = ftell(in);
    fseek(in, 0, SEEK_SET);
    uint8_t *data = malloc((size_t)file_size);
    if (!data || fread(data, 1, (size_t)file_size, in) != (size_t)file_size) die("read");
    fclose(in);
    if (file_size < 4 || data[0] != 0xff || data[1] != 0xd8) die("missing SOI");

    int precision = 0, width = 0, height = 0, components = 0;
    int predictor = 0, point = 0, scan_tables[4], scan_count = 0;
    size_t scan_at = 0;
    size_t pos = 2;
    while (pos + 4 <= (size_t)file_size) {
        if (data[pos] != 0xff) die("marker alignment");
        while (data[pos + 1] == 0xff) pos++;
        unsigned marker = data[pos + 1];
        if (marker == 0xd9) die("EOI before SOS");
        unsigned seglen = ((unsigned)data[pos + 2] << 8) | data[pos + 3];
        if (pos + 2 + seglen > (size_t)file_size) die("marker past end");
        const uint8_t *payload = data + pos + 4;
        if (marker == 0xda) {
            scan_count = payload[0];
            if (scan_count < 1 || scan_count > 4) die("bad component count");
            for (int i = 0; i < scan_count; i++) scan_tables[i] = payload[2 + 2 * i] >> 4;
            predictor = payload[1 + 2 * scan_count];
            int se = payload[2 + 2 * scan_count];
            int sal = payload[3 + 2 * scan_count];
            if (se != 0 || (sal & 0xf0)) die("not lossless sequential");
            point = sal & 0x0f;
            scan_at = pos + 2 + seglen;
            break;
        }
        if (marker == 0xc3) {
            precision = payload[0];
            height = (payload[1] << 8) | payload[2];
            width = (payload[3] << 8) | payload[4];
            components = payload[5];
            if (components < 1 || components > 4) die("bad frame");
            for (int i = 0; i < components; i++) {
                if (payload[7 + 3 * i] != 0x11) die("only 1x1 sampling");
            }
        } else if (marker == 0xc4) {
            size_t k = 0;
            size_t nbytes = seglen - 2;
            while (k < nbytes) {
                int ident = payload[k];
                if (ident & 0xf0) die("AC table");
                const uint8_t *counts = payload + k + 1;
                k += 17;
                int total = 0;
                for (int i = 0; i < 16; i++) total += counts[i];
                build_table(ident & 15, counts, payload + k);
                k += (size_t)total;
            }
        } else if (marker == 0xdd) {
            die("restart intervals are not decoded");
        } else if (marker == 0xc0 || marker == 0xc1 || marker == 0xc2) {
            die("lossy frame");
        }
        pos += 2 + seglen;
    }
    if (!precision || !scan_at) die("missing frame or scan");
    if (predictor != 1 || point != 0) die("only predictor 1 and Pt 0");
    if (scan_count != components) die("scan/frame mismatch");
    for (int i = 0; i < scan_count; i++) if (!have_table[scan_tables[i]]) die("missing table");

    size_t entropy_n = 0;
    uint8_t *entropy = unstuff(data + scan_at, (size_t)file_size - scan_at, &entropy_n);
    size_t cursor = 0;
    uint64_t acc = 0;
    int bits = 0;
    int table = scan_tables[0];
    for (int i = 1; i < scan_count; i++) if (scan_tables[i] != table) die("mixed Huffman tables");

    size_t samples = (size_t)height * (size_t)width * (size_t)components;
    uint16_t *out = malloc(samples * sizeof(uint16_t));
    if (!out) die("out of memory");
    int mask = (1 << precision) - 1;
    int seed = 1 << (precision - 1);
    int *left = calloc((size_t)components, sizeof(int));
    int *above0 = calloc((size_t)components, sizeof(int));
    if (!left || !above0) die("out of memory");

    size_t written = 0;
    for (int y = 0; y < height; y++) {
        for (int x = 0; x < width; x++) {
            for (int c = 0; c < components; c++) {
                while (bits < 16) {
                    acc = (acc << 8) | entropy[cursor++];
                    bits += 8;
                }
                unsigned prefix = (unsigned)((acc >> (bits - 16)) & 65535);
                int length = lengths[table][prefix];
                int symbol = symbols[table][prefix];
                if (length == 0) die("invalid Huffman prefix");
                bits -= length;
                int diff;
                if (symbol == 0) diff = 0;
                else if (symbol == 16) diff = -32768;
                else {
                    while (bits < symbol) {
                        acc = (acc << 8) | entropy[cursor++];
                        bits += 8;
                    }
                    bits -= symbol;
                    int magnitude = (int)((acc >> bits) & ((1u << symbol) - 1));
                    diff = magnitude >= (1 << (symbol - 1)) ? magnitude : magnitude - ((1 << symbol) - 1);
                }
                if (bits) acc &= (1ull << bits) - 1;
                else acc = 0;
                int prediction;
                if (y == 0 && x == 0) prediction = seed;
                else if (y == 0) prediction = left[c];
                else if (x == 0) prediction = above0[c];
                else prediction = left[c];
                int value = (prediction + diff) & mask;
                left[c] = value;
                if (x == 0) above0[c] = value;
                out[written++] = (uint16_t)value;
            }
        }
    }
    FILE *fp = fopen(argv[2], "wb");
    if (!fp || fwrite(out, sizeof(uint16_t), samples, fp) != samples) die("write");
    fclose(fp);
    printf("precision=%d sof_w=%d sof_h=%d components=%d predictor=%d point=%d out_w=%d out_h=%d samples=%zu\n",
           precision, width, height, components, predictor, point, width * components, height, samples);
    return 0;
}
