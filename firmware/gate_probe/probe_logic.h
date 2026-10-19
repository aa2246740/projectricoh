#ifndef GATE_PROBE_LOGIC_H
#define GATE_PROBE_LOGIC_H
#include <stdint.h>

/* Shared by the firmware body and the host truth-table tests.
 * The firmware supplies volatile loads. The host supplies counting stubs
 * and never calls gxr_list_paint. */

#define PROBE_ADDR_WORD 0x205d9bf8u
#define PROBE_ADDR_TYPE 0x2022f71cu
#define PROBE_ADDR_PART 0x205a280fu
#define PROBE_ADDR_COUNT 0x205a27d4u
#define PROBE_ADDR_ENTRIES 0x205a27d8u
#define PROBE_ADDR_REENTRY 0x200546ffu
#define PROBE_ENTRIES_LO 0x205a0000u
#define PROBE_ENTRIES_HI 0x205c0000u
#define PROBE_TAG_IMAGE 33u
#define PROBE_GLYPH_BYTES 96u
#define PROBE_ROWS 16u

typedef struct {
    uint32_t word;
    uint32_t entries;
    uint32_t state;
    uint32_t verdict;
    uint8_t type;
    uint8_t part;
    uint8_t count;
    uint8_t tag;
    uint8_t dereferenced;
} ProbeView;

#ifndef PROBE_HOST
static inline uint8_t probe_load_u8(uint32_t address)
{
    return *(volatile uint8_t *)(uintptr_t)address;
}
static inline uint32_t probe_load_u32(uint32_t address)
{
    return *(volatile uint32_t *)(uintptr_t)address;
}
static inline void probe_store_u8(uint32_t address, uint8_t value)
{
    *(volatile uint8_t *)(uintptr_t)address = value;
}
#else
uint8_t probe_load_u8(uint32_t address);
uint32_t probe_load_u32(uint32_t address);
#endif

static inline void probe_decide(ProbeView *view)
{
    uint32_t entries = view->entries;
    uint8_t count = view->count;
    uint32_t ent;

    view->verdict = 0;
    view->tag = 0;
    view->state = 0;
    view->dereferenced = 0;
    if (view->word != 8 || view->part != 2 || count < 1 || count > 2 ||
        view->type != 5 || entries == 0 || (entries & 3u) != 0 ||
        entries < PROBE_ENTRIES_LO || entries >= PROBE_ENTRIES_HI)
        return;
    ent = entries + (uint32_t)(count - 1u) * 8u;
    view->dereferenced = 1;
    view->tag = probe_load_u8(ent);
    view->state = probe_load_u32(ent + 4u);
    if (view->tag == PROBE_TAG_IMAGE && view->state == PROBE_ADDR_TYPE)
        view->verdict = 1;
}

static const char probe_hex[] = "0123456789ABCDEF";

static inline void probe_put_hex2(char *out, uint32_t value)
{
    out[0] = probe_hex[(value >> 4) & 0xfu];
    out[1] = probe_hex[value & 0xfu];
}

static inline void probe_put_hex8(char *out, uint32_t value)
{
    unsigned i;
    for (i = 0; i < 8; ++i)
        out[7u - i] = probe_hex[(value >> (4u * i)) & 0xfu];
}

/* Row 0..8 are A T P C G0 S V W E. Rows 9..15 are the eight-dot placeholder. */
static inline void probe_format_row(unsigned row, const ProbeView *view, char *out)
{
    unsigned i;
    for (i = 0; i < 16; ++i) out[i] = 0;
    if (row >= 9 && row < PROBE_ROWS) {
        for (i = 0; i < 8; ++i) out[i] = '.';
        return;
    }
    if (row == 0) {
        out[0] = 'A'; out[1] = '=';
        probe_put_hex2(out + 2, view->word & 0xffu);
    } else if (row == 1) {
        out[0] = 'T'; out[1] = '=';
        probe_put_hex2(out + 2, view->type);
    } else if (row == 2) {
        out[0] = 'P'; out[1] = '=';
        probe_put_hex2(out + 2, view->part);
    } else if (row == 3) {
        out[0] = 'C'; out[1] = '=';
        probe_put_hex2(out + 2, view->count);
    } else if (row == 4) {
        out[0] = 'G'; out[1] = '0'; out[2] = '=';
        if (!view->dereferenced) {
            out[3] = '-'; out[4] = '-';
        } else {
            probe_put_hex2(out + 3, view->tag);
        }
    } else if (row == 5) {
        out[0] = 'S'; out[1] = '=';
        if (!view->dereferenced) {
            for (i = 0; i < 8; ++i) out[2u + i] = '-';
        } else {
            probe_put_hex8(out + 2, view->state);
        }
    } else if (row == 6) {
        out[0] = 'V'; out[1] = '=';
        probe_put_hex2(out + 2, view->verdict & 0xffu);
    } else if (row == 7) {
        out[0] = 'W'; out[1] = '=';
        probe_put_hex8(out + 2, view->word);
    } else if (row == 8) {
        out[0] = 'E'; out[1] = '=';
        probe_put_hex8(out + 2, view->entries);
    }
}
#endif
