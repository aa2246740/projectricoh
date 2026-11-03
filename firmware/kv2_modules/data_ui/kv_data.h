#ifndef KV_DATA_H
#define KV_DATA_H

#include <stddef.h>
#include <stdint.h>
#include "knobs.h"

enum {
    KV_DATA_BYTES = 17384, KV_DATA_HEADER = 64,
    KV_DATA_UNITS = 3, KV_DATA_RECIPES = 24, KV_DATA_ITEMS = 201,
    KV_DATA_POINTS = 3430, KV_DATA_CONTROLS = 10, KV_DATA_MAX_POINTS = 19,
    KV_DATA_RECIPE_OFFSET = 64, KV_DATA_ITEM_OFFSET = 448,
    KV_DATA_POINT_OFFSET = 3664, KV_DATA_RECORD = 16
};

/* This type replaces the old eleven-byte session type at integration. */
typedef struct { int16_t v[KV_DATA_CONTROLS]; } UvLevels;
_Static_assert(sizeof(UvLevels) == 20, "session levels occupy twenty bytes");

/* Publish only through kv_data_open. Keep the backing bytes immutable and live. */
typedef struct { const uint8_t *bytes; uint32_t length; } KvDataView;
typedef struct {
    uint8_t unit, slot, item_count, display[9];
    uint16_t first_item;
} KvDataRecipe;
typedef struct {
    uint8_t control, point_count, cap_flags, amount_step;
    int16_t min_level, max_level, default_level;
    uint32_t points_offset;
} KvDataItem;
typedef struct { int16_t level, dose; } KvDataPoint;

/* All functions return zero on success, -1 on rejection. Failure keeps out intact.
 * Link the existing gxr2_crc_zeroed implementation used by gen 127. */
int kv_data_open(const uint8_t *bytes, size_t length, KvDataView *out);
int kv_data_recipe(const KvDataView *, unsigned unit, unsigned slot, KvDataRecipe *out);
int kv_data_item(const KvDataView *, unsigned index, KvDataItem *out);
int kv_data_find(const KvDataView *, unsigned unit, unsigned slot,
                 unsigned control, KvDataItem *out);
int kv_data_point(const KvDataView *, const KvDataItem *, unsigned index, KvDataPoint *out);
int kv_data_request(const KvDataView *, unsigned unit, unsigned slot,
                    const UvLevels *, KvRequest *out);

#endif
