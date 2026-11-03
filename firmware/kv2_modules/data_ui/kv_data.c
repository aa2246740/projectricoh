#include "kv_data.h"

uint32_t gxr2_crc_zeroed(const uint8_t *, size_t, size_t, size_t);

static uint16_t read16(const uint8_t *p)
{ return (uint16_t)((uint16_t)p[0] << 8 | p[1]); }
static uint32_t read32(const uint8_t *p)
{ return (uint32_t)p[0] << 24 | (uint32_t)p[1] << 16 | (uint32_t)p[2] << 8 | p[3]; }
static int16_t reads16(const uint8_t *p)
{
    uint16_t n = read16(p);
    return (int16_t)(n <= INT16_MAX ? (int32_t)n : (int32_t)n - 65536);
}
static int within(size_t total, size_t offset, size_t length)
{ return offset <= total && length <= total - offset; }
static int all_zero(const uint8_t *p, unsigned count)
{
    unsigned i;
    for (i = 0; i < count; ++i) if (p[i]) return 0;
    return 1;
}
static int ready(const KvDataView *v)
{ return v && v->bytes && v->length == KV_DATA_BYTES; }

static unsigned item_count(unsigned slot)
{ return slot == 3 ? 5u : slot == 4 ? 8u : 9u; }
static unsigned item_control(unsigned slot, unsigned index)
{
    if (slot == 3) return index == 4 ? 9u : index + 1;
    return slot == 4 ? index + 1 : index;
}

/* Small range metadata, independent of the variable dose table. */
static unsigned amount_step(unsigned unit, unsigned slot)
{
    static const uint8_t steps[3][8] = {
        {25,25,0,0,20,10,20,25},
        {25,25,0,0,20,10,20,25},
        {20,25,0,0,10,10,10,10}
    };
    return steps[unit][slot - 1];
}
static int upper_level(unsigned unit, unsigned slot, unsigned control)
{
    if (control == 0) return 150;
    if (control == 2 && slot == 3 && unit < 2) return 8;
    if (control == 5) {
        if (slot == 1) return unit == 2 ? 8 : 6;
        if (slot == 4) return unit == 0 ? 5 : 6;
        if (slot == 8 && unit < 2) return 8;
    }
    return 9;
}

static int validate_item(const uint8_t *bytes, size_t total, const uint8_t *p,
                         unsigned unit, unsigned slot, unsigned control,
                         uint32_t *next_point)
{
    unsigned count = p[1], step = control == 0 ? amount_step(unit, slot) : 0;
    unsigned j, found = 0, expected_count;
    int lo = control == 0 || control == 4 ? 0 : -9;
    int hi = upper_level(unit, slot, control), def = control == 0 ? 100 : 0;
    int cap = control != 0 && control != 4 && hi < 9 ? 2 : 0;
    int dose_min = control == 0 || control == 4 ? 0 :
                   control <= 3 || control == 5 ? -16384 : -4096;
    int dose_max = control == 0 ? 150 :
                   control <= 3 || control == 5 ? 16384 : 4096;
    int previous_level = -32768, previous_dose = -32768;
    uint32_t offset = read32(p + 12);
    expected_count = control == 0 ? (150u + step - 1u) / step + 1u : (unsigned)(hi - lo + 1);
    if (p[0] != control || count < 1 || count > KV_DATA_MAX_POINTS ||
        count != expected_count || reads16(p + 2) != lo || reads16(p + 4) != hi ||
        reads16(p + 6) != def || p[8] != cap || p[9] != step || read16(p + 10) ||
        (offset & 3u) || offset != *next_point ||
        !within(total, offset, (size_t)count * 4u)) return -1;
    for (j = 0; j < count; ++j) {
        const uint8_t *point = bytes + offset + 4u * j;
        int level = reads16(point), dose = reads16(point + 2);
        int expected = control == 0 ? (int)(j * step) : lo + (int)j;
        if (expected > 150 && control == 0) expected = 150;
        if (level != expected || level <= previous_level || dose <= previous_dose ||
            dose < dose_min || dose > dose_max || (control == 0 && dose != level)) return -1;
        if (level == def) {
            if (dose != (control == 0 ? 100 : 0)) return -1;
            found = 1;
        }
        previous_level = level;
        previous_dose = dose;
    }
    if (!found) return -1;
    *next_point += count * 4u;
    return 0;
}

int kv_data_open(const uint8_t *bytes, size_t length, KvDataView *out)
{
    static const uint8_t magic[8] = {'G','X','K','V','2','R','2',0};
    KvDataView result;
    unsigned i, j, k, first = 0;
    uint32_t next_point = KV_DATA_POINT_OFFSET;
    if (!bytes || !out || length != KV_DATA_BYTES ||
        !within(length, 0, KV_DATA_HEADER)) return -1;
    for (i = 0; i < 8; ++i) if (bytes[i] != magic[i]) return -1;
    if (read16(bytes + 8) != 1 || read16(bytes + 10) != KV_DATA_HEADER ||
        read32(bytes + 12) != length || read16(bytes + 20) != KV_DATA_UNITS ||
        read16(bytes + 22) != KV_DATA_RECIPES || read16(bytes + 24) != KV_DATA_ITEMS ||
        read16(bytes + 26) != KV_DATA_POINTS || read16(bytes + 28) != KV_DATA_RECORD ||
        read16(bytes + 30) != KV_DATA_RECORD || read16(bytes + 32) != 4 ||
        read16(bytes + 34) != 4096 || read32(bytes + 36) != KV_DATA_RECIPE_OFFSET ||
        read32(bytes + 40) != KV_DATA_ITEM_OFFSET || read32(bytes + 44) != KV_DATA_POINT_OFFSET ||
        read16(bytes + 48) || read16(bytes + 50) != 1 ||
        read16(bytes + 52) != KV_DATA_CONTROLS || read16(bytes + 54) ||
        !all_zero(bytes + 56, 8)) return -1;
    if ((read32(bytes + 36) & 3u) || (read32(bytes + 40) & 3u) ||
        (read32(bytes + 44) & 3u) ||
        !within(length, read32(bytes + 36), KV_DATA_RECIPES * KV_DATA_RECORD) ||
        !within(length, read32(bytes + 40), KV_DATA_ITEMS * KV_DATA_RECORD) ||
        !within(length, read32(bytes + 44), KV_DATA_POINTS * 4u) ||
        read32(bytes + 16) != gxr2_crc_zeroed(bytes, length, 16, 4)) return -1;
    for (i = 0; i < KV_DATA_RECIPES; ++i) {
        const uint8_t *recipe = bytes + KV_DATA_RECIPE_OFFSET + i * KV_DATA_RECORD;
        unsigned unit = i / 8, slot = i % 8 + 1, count = item_count(slot);
        unsigned controls = 0, display = 0;
        if (recipe[0] != unit || recipe[1] != slot || recipe[2] != count ||
            recipe[3] || read16(recipe + 4) != first || recipe[15] ||
            first > KV_DATA_ITEMS || count > KV_DATA_ITEMS - first) return -1;
        for (j = 0; j < count; ++j) {
            const uint8_t *item = bytes + KV_DATA_ITEM_OFFSET + (first + j) * KV_DATA_RECORD;
            unsigned control = item_control(slot, j);
            controls |= 1u << control;
            if (validate_item(bytes, length, item, unit, slot, control, &next_point)) return -1;
        }
        for (k = 0; k < 9; ++k) {
            unsigned control = recipe[6 + k];
            if (k >= count) { if (control != 255) return -1; }
            else {
                if (control >= KV_DATA_CONTROLS || !(controls & (1u << control)) ||
                    (display & (1u << control))) return -1;
                display |= 1u << control;
            }
        }
        if (display != controls) return -1;
        first += count;
    }
    if (first != KV_DATA_ITEMS || next_point != length) return -1;
    result.bytes = bytes;
    result.length = (uint32_t)length;
    *out = result;
    return 0;
}

int kv_data_recipe(const KvDataView *v, unsigned unit, unsigned slot, KvDataRecipe *out)
{
    KvDataRecipe result;
    const uint8_t *p;
    unsigned i;
    if (!ready(v) || !out || unit >= KV_DATA_UNITS || slot < 1 || slot > 8) return -1;
    p = v->bytes + KV_DATA_RECIPE_OFFSET + (unit * 8 + slot - 1) * KV_DATA_RECORD;
    result.unit = p[0]; result.slot = p[1]; result.item_count = p[2];
    result.first_item = read16(p + 4);
    for (i = 0; i < 9; ++i) result.display[i] = p[6 + i];
    *out = result;
    return 0;
}
int kv_data_item(const KvDataView *v, unsigned index, KvDataItem *out)
{
    KvDataItem result;
    const uint8_t *p;
    if (!ready(v) || !out || index >= KV_DATA_ITEMS) return -1;
    p = v->bytes + KV_DATA_ITEM_OFFSET + index * KV_DATA_RECORD;
    result.control = p[0]; result.point_count = p[1];
    result.min_level = reads16(p + 2); result.max_level = reads16(p + 4);
    result.default_level = reads16(p + 6); result.cap_flags = p[8];
    result.amount_step = p[9]; result.points_offset = read32(p + 12);
    *out = result;
    return 0;
}
int kv_data_find(const KvDataView *v, unsigned unit, unsigned slot,
                 unsigned control, KvDataItem *out)
{
    KvDataRecipe recipe;
    unsigned i;
    if (!out || control >= KV_DATA_CONTROLS || kv_data_recipe(v, unit, slot, &recipe)) return -1;
    for (i = 0; i < recipe.item_count; ++i) {
        KvDataItem item;
        if (kv_data_item(v, recipe.first_item + i, &item)) return -1;
        if (item.control == control) { *out = item; return 0; }
    }
    return -1;
}
int kv_data_point(const KvDataView *v, const KvDataItem *item,
                  unsigned index, KvDataPoint *out)
{
    KvDataPoint result;
    size_t length;
    const uint8_t *p;
    if (!ready(v) || !item || !out || item->point_count < 1 ||
        item->point_count > KV_DATA_MAX_POINTS || index >= item->point_count ||
        item->points_offset < KV_DATA_POINT_OFFSET || (item->points_offset & 3u)) return -1;
    length = (size_t)item->point_count * 4u;
    if (!within(v->length, item->points_offset, length)) return -1;
    p = v->bytes + item->points_offset + index * 4u;
    result.level = reads16(p); result.dose = reads16(p + 2);
    *out = result;
    return 0;
}
int kv_data_request(const KvDataView *v, unsigned unit, unsigned slot,
                    const UvLevels *levels, KvRequest *out)
{
    KvRequest result = {100, {0}, 0, 0};
    KvDataRecipe recipe;
    unsigned i, j, seen = 0;
    if (!levels || !out || kv_data_recipe(v, unit, slot, &recipe)) return -1;
    for (i = 0; i < recipe.item_count; ++i) {
        KvDataItem item;
        int found = 0;
        if (kv_data_item(v, recipe.first_item + i, &item)) return -1;
        for (j = 0; j < item.point_count; ++j) {
            KvDataPoint point;
            if (kv_data_point(v, &item, j, &point)) return -1;
            if (point.level == levels->v[item.control]) {
                if (!item.control) result.amount = point.dose;
                else result.dose[item.control - 1] = point.dose;
                found = 1;
                break;
            }
        }
        if (!found) return -1;
        seen |= 1u << item.control;
    }
    for (i = 0; i < KV_DATA_CONTROLS; ++i)
        if (!(seen & (1u << i)) && levels->v[i] != (i == 0 ? 100 : 0)) return -1;
    *out = result;
    return 0;
}
