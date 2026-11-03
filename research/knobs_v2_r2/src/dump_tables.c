#include "../tables/knobs_v2_r2_tables.h"
#include <stdio.h>

int main(void)
{
    int i, j;
    printf("{\"schema\":\"%s\",\"q\":%d,\"max_points\":%d,\"wb_method\":%d,\"split_method\":%d,\"units\":[",
           KV2_SCHEMA, KV2_Q, KV2_MAX_POINTS, KV2_WB_METHOD, KV2_SPLIT_METHOD);
    for (i = 0; i < KV2_UNIT_COUNT; i++) printf("%s\"%s\"", i ? "," : "", kv2_units[i]);
    printf("],\"controls\":[");
    for (i = 0; i < KV2_CONTROL_COUNT; i++) {
        const Kv2Control *c = &kv2_controls[i];
        printf("%s{\"id\":%d,\"name\":\"%s\",\"label\":\"%s\",\"dose_index\":%d}",
               i ? "," : "", i, c->name, c->label, c->dose_index);
    }
    printf("],\"recipes\":[");
    for (i = 0; i < KV2_RECIPE_COUNT; i++) {
        const Kv2Recipe *r = &kv2_recipes[i];
        printf("%s{\"unit\":%d,\"slot\":%d,\"first_item\":%d,\"item_count\":%d}",
               i ? "," : "", r->unit, r->slot, r->first_item, r->item_count);
    }
    printf("],\"items\":[");
    for (i = 0; i < KV2_ITEM_COUNT; i++) {
        const Kv2Item *a = &kv2_items[i];
        printf("%s{\"control\":%d,\"point_count\":%d,\"min_level\":%d,\"max_level\":%d,\"default_level\":%d,\"cap_lower\":%d,\"cap_upper\":%d,\"amount_step\":%d,\"points\":[",
               i ? "," : "", a->control, a->point_count, a->min_level, a->max_level,
               a->default_level, a->cap_lower, a->cap_upper, a->amount_step);
        for (j = 0; j < a->point_count; j++) printf("%s{\"level\":%d,\"dose\":%d}",
                                                j ? "," : "", a->points[j].level, a->points[j].dose);
        printf("]}");
    }
    puts("]}");
    return 0;
}
