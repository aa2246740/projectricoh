#include "deep_isp.h"
#include "foreign.h"

#ifndef RECIPE_FW_HOST
/* Calls made from this file use bl. Callers elsewhere keep their 2e code. */
uint32_t rv1_crc32(const uint8_t *, size_t) RFW_NEAR;
void *gxr_alloc(uint32_t) RFW_NEAR;
int32_t gxr_rpc_ready(void) RFW_NEAR;
int32_t gxr_rpc_limit(void) RFW_NEAR;
int32_t gxr_thread_context(void) RFW_NEAR;
const volatile uint8_t *gxr_unit_info(uint32_t) RFW_NEAR;
int32_t rfw_rpc8_native(uint32_t, uint32_t) RFW_NEAR;
uint32_t rfw_rpc8_preflight(void) RFW_NEAR;
int32_t rfw_rpc8_call(uint32_t, uint32_t) RFW_NEAR;
unsigned rfw_deep_id(const Rv1Recipe *) RFW_NEAR;
uint32_t rfw_deep_ownership(void) RFW_NEAR;
#endif

static uint16_t be16(const volatile uint8_t *p)
{ return (uint16_t)((uint16_t)p[0] << 8 | p[1]); }

uint32_t rfw_rpc8_preflight(void)
{
    const volatile uint8_t *info;
    static const uint8_t unit_name[8] = {'j','l','a','u','n','c','h',0};
    unsigned i;
    if (gxr_thread_context() != 0 || gxr_rpc_ready() == 0 || gxr_rpc_limit() <= 8)
        return 0;
    info = gxr_unit_info(1);
#ifndef RECIPE_FW_HOST
    if ((uintptr_t)info != UINT32_C(0x2040f818)) return 0;
#else
    if (info == NULL) return 0;
#endif
    for (i = 0; i < 8; ++i)
        if (info[4 + i] != unit_name[i]) return 0;
    return be16(info + 0x30) == 0x0151 && be16(info + 0x32) == 0;
}

int32_t rfw_rpc8_call(uint32_t letter_idx, uint32_t value)
{
    if (letter_idx < 21 || letter_idx > 23 || value > 65535 || !rfw_rpc8_preflight())
        return -32768;
    return rfw_rpc8_native(letter_idx, value);
}

unsigned rfw_deep_id(const Rv1Recipe *recipe)
{
#if RFW_DEEP_ENABLED
    unsigned profile, i;
    if (recipe == NULL) return 0;
    for (profile = 0; profile < RFW_DEEP_PROFILES; ++profile) {
        const uint8_t *p = (const uint8_t *)recipe;
        const uint8_t *key = (const uint8_t *)&rfw_defaults[rfw_deep_slots[profile] - 1];
        for (i = 0; i < sizeof(*recipe); ++i) if (p[i] != key[i]) break;
        if (i == sizeof(*recipe)) return profile + 1;
    }
#else
    (void)recipe;
#endif
    return 0;
}

#if RFW_DEEP_ENABLED
const char rfw_table_paths[2][19] = {"/ATA1/DEEPTBL0.DAT", "/ATA1/DEEPTBL1.DAT"};

const uint8_t *rfw_deep_data(const RfwDeepState *state, unsigned profile, const RfwDeepRow *r)
{
    if (profile == 0) return r->stock;
    return state->tables + (RFW_TABLE_HEADER - RFW_TABLE_ENTRY) + profile * RFW_TABLE_ENTRY + r->offset;
}

/* 1 when the big-endian word at stored equals value. */
static RFW_NEAR int same32(uint32_t value, const uint8_t *stored)
{
    unsigned i;
    for (i = 0; i < 4; ++i, value <<= 8)
        if (stored[i] != (uint8_t)(value >> 24)) return 0;
    return 1;
}

static RFW_NEAR int crc_is(const uint8_t *bytes, size_t n, const uint8_t *stored)
{ return same32(rv1_crc32(bytes, n), stored); }

/* Returns the file CRC, or 0 for any failure. Every byte is checked: the
 * CRC of the 12 header bytes must be RFW_TABLE_HEADER_CRC (that of "GXDT",
 * version 1, 7 entries, flags 0, 212-byte entries, reserved 0; a different
 * magic or version changes at most 5 bytes and always changes this CRC),
 * then the stored CRC of bytes 16..end, then per entry the slot key, the
 * bound recipe, three row CRCs and both curve shapes. */
static RFW_NEAR uint32_t table_valid(const uint8_t *t, size_t n)
{
    unsigned e, k, i, v, previous;
    const uint8_t *p = t + RFW_TABLE_HEADER;
    uint32_t crc;
    if (n != RFW_TABLE_BYTES || rv1_crc32(t, 12) != RFW_TABLE_HEADER_CRC) return 0;
    crc = rv1_crc32(p, RFW_TABLE_BYTES - RFW_TABLE_HEADER);
    if (crc == 0 || !same32(crc, t + 12)) return 0;
    for (e = 0; e < RFW_DEEP_PROFILES; ++e, p += RFW_TABLE_ENTRY) {
        unsigned slot = rfw_deep_slots[e];
        if (p[0] != slot ||
            !crc_is((const uint8_t *)&rfw_defaults[slot - 1], sizeof(Rv1Recipe), p + 4)) return 0;
        for (k = 0; k < RFW_DEEP_ROWS; ++k)
            if (!crc_is(p + rfw_deep_rows[k].offset, rfw_deep_rows[k].bytes, p + 8 + 4 * k)) return 0;
        /* A5: 31 strictly increasing inputs in 1..4094. B5: no decrease. */
        for (previous = 0, i = 20; i < 82; i += 2) {
            v = (unsigned)p[i] << 8 | p[i + 1];
            if (v <= previous || v > 4094) return 0;
            previous = v;
        }
        for (i = 83; i < 115; ++i) if (p[i] < p[i - 1]) return 0;
    }
    return crc;
}

static RFW_NEAR uint32_t load_table(uint8_t *t, unsigned which)
{
    size_t n;
    if (rfw_read_path(rfw_table_paths[which], t, RFW_TABLE_ALLOC, &n) != RV1_OK) return 0;
    return table_valid(t, n);
}

/* Two-file rule, as for the recipe banks: one valid file is enough; two valid
 * files that differ conflict; a lone DEEPTBL1 must read back identically.
 * DEEPTBL1 is read first so a valid DEEPTBL0 is what stays in RAM. */
RFW_LATE void rfw_deep_refresh(RfwDeepState *state)
{
    uint32_t crc0, crc1;
    if (state->active != 0 || state->uncertain) return;
    state->tables_ok = 0;
    if (state->tables == NULL) state->tables = gxr_alloc(RFW_TABLE_ALLOC);
    if (state->tables == NULL) return;
    crc1 = load_table(state->tables, 1);
    crc0 = load_table(state->tables, 0);
    if (crc0 == 0 && crc1 != 0) crc0 = load_table(state->tables, 1);
    state->tables_ok = crc0 != 0 && (crc1 == 0 || crc1 == crc0);
}

static int expect(uint32_t letter, uint32_t value, uint16_t expected)
{ return rfw_rpc8_call(letter, value) == (int32_t)expected; }

static int read_at(uint32_t address, uint16_t expected)
{
    uint16_t page = (uint16_t)(address >> 16);
    return expect(23, page, page) && expect(21, address & 65535, expected);
}
#else
void rfw_deep_refresh(RfwDeepState *state) { (void)state; }
#endif

RFW_LATE Rv1Status rfw_deep_transition(RfwDeepState *state, const Rv1Recipe *recipe)
{
#if RFW_DEEP_ENABLED
    unsigned row, offset, desired = state->tables_ok ? rfw_deep_id(recipe) : 0;
    if (state->uncertain) return RV1_CONFLICT;
    if (desired == state->active) return RV1_OK;
    if (!rfw_deep_ownership()) return RV1_CONFLICT;
    /* The last B5 halfword at 0x2013001c includes B6[0] at 0x2013001d.
     * Snapshot that actual byte once per resident session, never invent it. */
    if (!state->neighbor_valid) {
        int32_t value;
        if (!expect(23, 0x2013, 0x2013)) return RV1_CONFLICT;
        value = rfw_rpc8_call(21, 0x001c);
        if (value < 0 || value > 65535 ||
            (uint32_t)value >> 8 != rfw_deep_data(state, state->active, &rfw_deep_rows[1])[32])
            return RV1_CONFLICT;
        state->neighbor = (uint8_t)value;
        state->neighbor_valid = 1;
    }
    /* V positions the cursor without incrementing it. W stores, returns its
     * own lduh readback, then advances the full 32-bit cursor by two. Only the
     * first old halfword of each row is checked; this is not a full RAM audit.
     * Any failed response after the first attempted W is sticky. */
    for (row = 0; row < RFW_DEEP_ROWS; ++row) {
        const RfwDeepRow *r = &rfw_deep_rows[row];
        const uint8_t *p = rfw_deep_data(state, desired, r);
        if (!read_at(r->address, be16(rfw_deep_data(state, state->active, r))))
            return RV1_CONFLICT;
        for (offset = 0; offset < r->bytes; offset += 2) {
            uint16_t value = (uint16_t)p[offset] << 8;
            value |= offset + 1 < r->bytes ? p[offset + 1] : state->neighbor;
            state->uncertain = 1;
            if (!expect(22, value, value)) return RV1_CONFLICT;
        }
    }
    state->active = (uint8_t)desired;
    state->uncertain = 0;
#else
    (void)state;
    (void)recipe;
#endif
    return RV1_OK;
}
