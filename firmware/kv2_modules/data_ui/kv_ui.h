#ifndef KV_UI_H
#define KV_UI_H

#include "kv_data.h"

enum { KV_UI_PHYSICAL = 8, KV_UI_TEXT = 9, KV_UI_LEGACY_PARAMS = 11,
       KV_UI_LEGACY_RECORD = 24, KV_UI_NO_CONTROL = 255 };
enum { KV_UI_L1, KV_UI_CARD, KV_UI_ITEMS, KV_UI_VALUE, KV_UI_SCREENS };
enum { KV_UI_EVENT_NONE, KV_UI_EVENT_RECIPE, KV_UI_EVENT_MYREC, KV_UI_EVENT_DEFAULT };

/* Field layout matches gen 127's UvWindow. Link its actual uv_window function. */
typedef struct { uint8_t top, cursor; } KvUiWindow;
typedef struct {
    uint8_t screen, control, value_origin, armed;
    uint8_t current[KV_UI_SCREENS], top[KV_UI_SCREENS];
} KvUiNav;
typedef struct { uint8_t kind, slot; } KvUiEvent;
typedef struct {
    unsigned unit, slot, applied_slot, applied_user;
    const UvLevels *levels;
    const UvLevels *cache;             /* Eight vectors, required for L1. */
    const char *const *names;          /* Eight short names, one to five ASCII bytes. */
} KvUiModel;
typedef struct {
    char text[KV_UI_PHYSICAL][KV_UI_TEXT];
    uint8_t rows, logical_count, top, cursor, selectable;
} KvUiFrame;

/* Zero means success, -1 means rejection. Failed calls leave outputs intact. */
const char *kv_ui_label(unsigned control);
int kv_ui_default(const KvDataView *, unsigned unit, unsigned slot, UvLevels *out);
int kv_ui_adjusted(const KvDataView *, unsigned unit, unsigned slot,
                   const UvLevels *, int *out);
int kv_ui_value(const KvDataView *, unsigned unit, unsigned slot,
                unsigned control, int level, char out[KV_UI_TEXT]);
int kv_ui_compact(const KvDataView *, unsigned unit, unsigned slot,
                  unsigned left, unsigned right, const UvLevels *, char out[KV_UI_TEXT]);
int kv_ui_title(const KvDataView *, unsigned unit, unsigned slot,
                const UvLevels *, const char *name, char first, char out[KV_UI_TEXT]);
int kv_ui_value_cursor(const KvDataView *, unsigned unit, unsigned slot,
                       unsigned control, int level, unsigned *out);
unsigned kv_ui_count(const KvDataView *, unsigned unit, unsigned slot,
                     unsigned screen, unsigned control);
int kv_ui_window(unsigned count, unsigned current, unsigned previous, KvUiWindow *out);
int kv_ui_layout(unsigned count, unsigned current, unsigned previous, KvUiFrame *out);
int kv_ui_nav_init(const KvDataView *, unsigned unit, unsigned slot,
                   const UvLevels *, KvUiNav *out);
int kv_ui_render(const KvDataView *, const KvUiModel *, const KvUiNav *, KvUiFrame *out);
int kv_ui_move(const KvDataView *, unsigned unit, unsigned slot,
               const UvLevels *, const KvUiNav *, int delta, UvLevels *out_levels, KvUiNav *out_nav);
int kv_ui_native_move(const KvDataView *, unsigned unit, unsigned slot,
                      const UvLevels *, const KvUiNav *, unsigned physical,
                      UvLevels *out_levels, KvUiNav *out_nav);
int kv_ui_disp(const KvDataView *, unsigned unit, unsigned slot,
               const UvLevels *, const KvUiNav *, UvLevels *out_levels,
               KvUiNav *out_nav, KvUiEvent *out_event);
int kv_ui_native_disp(const KvDataView *, unsigned unit, unsigned slot,
                      const UvLevels *, const KvUiNav *, unsigned physical,
                      UvLevels *out_levels, KvUiNav *out_nav, KvUiEvent *out_event);

/* Structural conversion preserves the old four numbers. Validate the resulting
 * vector with kv_data_request before applying it under the new table. */
int kv_ui_legacy_levels(const int8_t old[KV_UI_LEGACY_PARAMS], UvLevels *out);
int kv_ui_legacy_record(const uint8_t *, size_t length, unsigned *slot, UvLevels *out);
int kv_ui_entry(const uint8_t record[KV_UI_LEGACY_RECORD], int applied, int adjusted,
                char out[KV_UI_TEXT]);

#endif
