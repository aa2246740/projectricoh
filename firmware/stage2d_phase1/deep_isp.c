#include "deep_isp.h"

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
static int expect(uint32_t letter, uint32_t value, uint16_t expected)
{ return rfw_rpc8_call(letter, value) == (int32_t)expected; }

static int read_at(uint32_t address, uint16_t expected)
{
    uint16_t page = (uint16_t)(address >> 16);
    return expect(23, page, page) && expect(21, address & 65535, expected);
}
#endif

Rv1Status rfw_deep_transition(RfwDeepState *state, const Rv1Recipe *recipe)
{
#if RFW_DEEP_ENABLED
    unsigned row, offset, desired = rfw_deep_id(recipe);
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
            (uint32_t)value >> 8 != rfw_deep_rows[1].data[state->active][32])
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
        const uint8_t *p = r->data[desired];
        if (!read_at(r->address, be16(r->data[state->active]))) return RV1_CONFLICT;
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
