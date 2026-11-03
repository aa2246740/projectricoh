#include "menu.h"
#include "../tables/knobs_v2_r2_tables.h"

int kv2_request(int unit, int slot, const int16_t *levels, int count, KvRequest *request)
{
    KvRequest r = {100, {0}, 0, 0};
    const Kv2Recipe *recipe;
    int i, j, found;
    if (!levels || !request || unit < 0 || unit >= KV2_UNIT_COUNT || slot < 1 || slot > 8) return -1;
    recipe = &kv2_recipes[unit * 8 + slot - 1];
    if (count != recipe->item_count) return -1;
    for (i = 0; i < count; i++) {
        const Kv2Item *item = &kv2_items[recipe->first_item + i];
        int index = kv2_controls[item->control].dose_index;
        found = 0;
        for (j = 0; j < item->point_count; j++) {
            if (item->points[j].level == levels[i]) {
                if (index < 0) r.amount = item->points[j].dose;
                else r.dose[index] = item->points[j].dose;
                found = 1;
                break;
            }
        }
        if (!found) return -1;
    }
    *request = r;
    return 0;
}

int kv2_apply(int unit, int slot, const int16_t *levels, int count,
              const uint8_t *stock, const uint8_t *base, uint8_t *out, KvStats *stats)
{
    KvRequest r;
    if (kv2_request(unit, slot, levels, count, &r)) return -1;
    return kv_apply(stock, base, &r, out, stats);
}
