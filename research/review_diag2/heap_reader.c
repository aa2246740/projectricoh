#include <stdint.h>
#include <stddef.h>
#include <stdlib.h>
#include "../../firmware/engine_diag_v2/resident/resident.h"
#include <string.h>

static uint8_t ram[0x800000];
static uint32_t addresses[20000], widths[20000], read_count;
static uint32_t marker, marker_hit, marker_seen;
static void (*on_read)(void);

static void record(uint32_t address, uint32_t width)
{
    if (address < 0x20000000u || address > 0x20800000u - width ||
        (width > 1 && (address & (width - 1u))) || read_count >= 20000u) abort();
    addresses[read_count] = address;
    widths[read_count++] = width;
}

static void after_read(uint32_t address)
{
    if (on_read && address == marker && ++marker_seen == marker_hit) {
        void (*fn)(void) = on_read;
        on_read = 0;
        fn();
    }
}

static uint32_t word(uint32_t address)
{
    uint32_t offset, value;
    record(address, 4);
    offset = address - 0x20000000u;
    value = ((uint32_t)ram[offset] << 24) | ((uint32_t)ram[offset + 1] << 16) |
        ((uint32_t)ram[offset + 2] << 8) | ram[offset + 3];
    after_read(address);
    return value;
}

static uint8_t byte(uint32_t address)
{
    uint8_t value;
    record(address, 1);
    value = ram[address - 0x20000000u];
    after_read(address);
    return value;
}

#define DH_WORD(a) word(a)
#define DH_BYTE(a) byte(a)
#include "../../firmware/engine_diag_v2/candidate/containers/product/diag_heap.h"

static DhSnapshot views[2];
static char rows[8][9];

void review_reset(void)
{
    memset(ram, 0, sizeof(ram));
    memset(views, 0, sizeof(views));
    read_count = marker = marker_hit = marker_seen = 0;
    on_read = 0;
}

void review_set(uint32_t address, uint32_t value, uint32_t width)
{
    uint32_t i;
    if (!width || width > 4u || address < 0x20000000u ||
        address > 0x20800000u - width) abort();
    for (i = 0; i < width; ++i)
        ram[address - 0x20000000u + i] = (uint8_t)(value >> (8u * (width - i - 1u)));
}

void review_hook(uint32_t address, uint32_t hit, void (*fn)(void))
{ marker = address; marker_hit = hit; marker_seen = 0; on_read = fn; }

void review_take(uint32_t pass)
{ if (pass > 1u) abort(); dh_take(&views[pass]); }

int review_equal(void)
{ return dh_equal(&views[0], &views[1]); }

const char *review_row(uint32_t index)
{
    memset(rows, 0, sizeof(rows));
    memcpy(rows[0], review_equal() ? "H0001 S" : "H0001 C", 7);
    dh_rows(&views[1], rows);
    return index < 8u ? rows[index] : 0;
}

uint32_t review_value(uint32_t field)
{
    const DhSnapshot *s = &views[1];
    switch (field) {
    case 0: return s->physical_hops;
    case 1: return s->free_hops;
    case 2: return read_count;
    case 3: return sizeof(DhSnapshot);
    case 4: return s->bad;
    case 5: return s->used_count;
    case 6: return s->used_bytes;
    case 7: return s->free_count;
    case 8: return s->free_bytes;
    case 9: return s->largest;
    case 10: return s->native_bits;
    case 11: return s->stale_bits;
    default: return 0;
    }
}

uint32_t review_read(uint32_t index, uint32_t field)
{ if (index >= read_count) abort(); return field ? widths[index] : addresses[index]; }
