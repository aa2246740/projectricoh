#include "kv_ui.h"

/* This is supplied by gen 127's ui_v2_data.c, not implemented here. */
void uv_window(unsigned, unsigned, unsigned, KvUiWindow *);

static void text_copy(char out[9], const char in[9])
{ unsigned i; for (i = 0; i < 9; ++i) out[i] = in[i]; }
static void text_trim(char text[9])
{
    unsigned n = 0;
    while (n < 8 && text[n]) ++n;
    while (n && text[n - 1] == ' ') text[--n] = 0;
}
static int levels_valid(const KvDataView *v, unsigned unit, unsigned slot, const UvLevels *levels)
{ KvRequest r; return kv_data_request(v, unit, slot, levels, &r) == 0; }
static int find_level(const KvDataView *v, const KvDataItem *item, int level, unsigned *index)
{
    unsigned j;
    for (j = 0; j < item->point_count; ++j) {
        KvDataPoint point;
        if (kv_data_point(v, item, j, &point)) return -1;
        if (point.level == level) { if (index) *index = j; return 0; }
    }
    return -1;
}
static int endpoint(const KvDataItem *item, int level)
{ return level == item->min_level || level == item->max_level; }

const char *kv_ui_label(unsigned control)
{
    static const char labels[10][5] = {"Amt","Cont","High","Shad","Fade",
                                      "Satu","Warm","Tint","Splt","Filt"};
    return control < 10 ? labels[control] : 0;
}
int kv_ui_default(const KvDataView *v, unsigned unit, unsigned slot, UvLevels *out)
{
    KvDataRecipe recipe;
    UvLevels result = {{100,0,0,0,0,0,0,0,0,0}};
    unsigned i;
    if (!out || kv_data_recipe(v, unit, slot, &recipe)) return -1;
    for (i = 0; i < recipe.item_count; ++i) {
        KvDataItem item;
        if (kv_data_item(v, recipe.first_item + i, &item)) return -1;
        result.v[item.control] = item.default_level;
    }
    *out = result;
    return 0;
}
int kv_ui_adjusted(const KvDataView *v, unsigned unit, unsigned slot,
                   const UvLevels *levels, int *out)
{
    UvLevels defaults;
    unsigned i;
    int result = 0;
    if (!out || !levels_valid(v, unit, slot, levels) || kv_ui_default(v, unit, slot, &defaults)) return -1;
    for (i = 0; i < KV_DATA_CONTROLS; ++i) if (levels->v[i] != defaults.v[i]) result = 1;
    *out = result;
    return 0;
}
int kv_ui_value(const KvDataView *v, unsigned unit, unsigned slot,
                unsigned control, int level, char out[9])
{
    KvDataItem item;
    char text[9] = {0};
    const char *label = kv_ui_label(control);
    unsigned i;
    if (!out || !label || kv_data_find(v, unit, slot, control, &item) ||
        find_level(v, &item, level, 0)) return -1;
    if (control == 0) {
        text[0] = 'A'; text[1] = 'm'; text[2] = 't';
        text[3] = endpoint(&item, level) ? '!' : ' ';
        text[4] = level >= 100 ? (char)('0' + level / 100) : ' ';
        text[5] = level >= 10 ? (char)('0' + level / 10 % 10) : ' ';
        text[6] = (char)('0' + level % 10); text[7] = '%';
    } else {
        for (i = 0; i < 4; ++i) text[i] = label[i];
        text[4] = endpoint(&item, level) ? '!' : ' ';
        text[5] = ' '; text[6] = level < 0 ? '-' : level > 0 ? '+' : ' ';
        text[7] = (char)('0' + (level < 0 ? -level : level));
    }
    text_copy(out, text);
    return 0;
}
static int compact_cell(const KvDataView *v, unsigned unit, unsigned slot,
                         unsigned control, const UvLevels *levels, char text[4])
{
    static const char letters[10] = {'A','C','H','S','F','V','W','T','P','G'};
    KvDataItem item;
    int level;
    if (control == 0 || control >= 10 || kv_data_find(v, unit, slot, control, &item)) return -1;
    level = levels->v[control];
    if (find_level(v, &item, level, 0)) return -1;
    text[0] = letters[control]; text[1] = level < 0 ? '-' : level > 0 ? '+' : ' ';
    text[2] = (char)('0' + (level < 0 ? -level : level));
    text[3] = endpoint(&item, level) ? '!' : ' ';
    return 0;
}
int kv_ui_compact(const KvDataView *v, unsigned unit, unsigned slot,
                  unsigned left, unsigned right, const UvLevels *levels, char out[9])
{
    char text[9] = {0};
    if (!out || !levels_valid(v, unit, slot, levels) ||
        compact_cell(v, unit, slot, left, levels, text)) return -1;
    if (right != KV_UI_NO_CONTROL) {
        if (right == left || compact_cell(v, unit, slot, right, levels, text + 4)) return -1;
    }
    text_trim(text);
    text_copy(out, text);
    return 0;
}
int kv_ui_title(const KvDataView *v, unsigned unit, unsigned slot,
                const UvLevels *levels, const char *name, char first, char out[9])
{
    char text[9] = {0};
    unsigned i;
    int changed;
    if (!out || !name || (first != '<' && first != '>' && first != ' ') ||
        kv_ui_adjusted(v, unit, slot, levels, &changed)) return -1;
    for (i = 0; i <= 5 && name[i]; ++i)
        if ((unsigned char)name[i] < 32 || (unsigned char)name[i] > 126) return -1;
    if (i == 0 || i > 5) return -1;
    text[0] = first; text[1] = (char)('0' + slot); text[2] = changed ? '*' : ' ';
    for (i = 0; name[i]; ++i) text[3 + i] = name[i];
    text_copy(out, text);
    return 0;
}
int kv_ui_value_cursor(const KvDataView *v, unsigned unit, unsigned slot,
                       unsigned control, int level, unsigned *out)
{
    KvDataItem item;
    unsigned index;
    if (!out || kv_data_find(v, unit, slot, control, &item) || find_level(v, &item, level, &index)) return -1;
    *out = item.point_count - 1u - index;
    return 0;
}
static unsigned card_controls(const KvDataRecipe *recipe, uint8_t controls[9])
{
    unsigned i, count = 0;
    for (i = 0; i < recipe->item_count; ++i)
        if (recipe->display[i] != 0) controls[count++] = recipe->display[i];
    return count;
}
unsigned kv_ui_count(const KvDataView *v, unsigned unit, unsigned slot,
                     unsigned screen, unsigned control)
{
    KvDataRecipe recipe;
    KvDataItem item;
    uint8_t controls[9];
    unsigned count;
    if (kv_data_recipe(v, unit, slot, &recipe)) return 0;
    switch (screen) {
    case KV_UI_L1: return 10;
    case KV_UI_CARD:
        count = card_controls(&recipe, controls);
        return 2 + (count + 1) / 2 + (count != recipe.item_count);
    case KV_UI_ITEMS: return 1u + recipe.item_count;
    case KV_UI_VALUE:
        return kv_data_find(v, unit, slot, control, &item) ? 0 : item.point_count;
    default: return 0;
    }
}
int kv_ui_window(unsigned count, unsigned current, unsigned previous, KvUiWindow *out)
{
    KvUiWindow result;
    if (!out || count < 1 || count > 33 || current >= count) return -1;
    uv_window(count, current, previous, &result);
    *out = result;
    return 0;
}
int kv_ui_layout(unsigned count, unsigned current, unsigned previous, KvUiFrame *out)
{
    KvUiFrame result = {0};
    KvUiWindow window;
    unsigned i;
    if (!out || kv_ui_window(count, current, previous, &window)) return -1;
    result.rows = KV_UI_PHYSICAL; result.logical_count = (uint8_t)count;
    result.top = window.top; result.cursor = window.cursor;
    for (i = 0; i < KV_UI_PHYSICAL; ++i) {
        result.text[i][0] = ' ';
        if (window.top + i < count) result.selectable |= (uint8_t)(1u << i);
    }
    *out = result;
    return 0;
}
static int nav_valid(const KvDataView *v, unsigned unit, unsigned slot,
                      const UvLevels *levels, const KvUiNav *nav)
{
    unsigned count, current;
    if (!nav || nav->screen >= KV_UI_SCREENS || nav->control >= KV_DATA_CONTROLS ||
        nav->armed > 1 || (nav->value_origin != KV_UI_CARD && nav->value_origin != KV_UI_ITEMS) ||
        !levels_valid(v, unit, slot, levels)) return 0;
    count = kv_ui_count(v, unit, slot, nav->screen, nav->control);
    if (!count || nav->current[nav->screen] >= count) return 0;
    if (nav->screen == KV_UI_VALUE &&
        (kv_ui_value_cursor(v, unit, slot, nav->control, levels->v[nav->control], &current) ||
         current != nav->current[KV_UI_VALUE])) return 0;
    return 1;
}
int kv_ui_nav_init(const KvDataView *v, unsigned unit, unsigned slot,
                   const UvLevels *levels, KvUiNav *out)
{
    KvUiNav result = {0};
    if (!out || !levels_valid(v, unit, slot, levels)) return -1;
    result.screen = KV_UI_CARD; result.control = 1; result.value_origin = KV_UI_ITEMS;
    result.current[KV_UI_L1] = (uint8_t)(slot - 1); result.current[KV_UI_CARD] = 1;
    *out = result;
    return 0;
}
static int logical_text(const KvDataView *v, const KvUiModel *model,
                        const KvUiNav *nav, unsigned row, char out[9])
{
    KvDataRecipe recipe;
    uint8_t controls[9];
    unsigned i, count, pairs;
    char text[9] = {0};
    if (kv_data_recipe(v, model->unit, model->slot, &recipe)) return -1;
    switch (nav->screen) {
    case KV_UI_L1:
        if (row < 8) {
            if (!model->cache) return -1;
            return kv_ui_title(v, model->unit, row + 1, model->cache + row, model->names[row],
                               !model->applied_user && model->applied_slot == row + 1 ? '>' : ' ', out);
        }
        if (row == 8) text_copy(text, " DISP:Tw");
        else {
            const char *name = model->applied_user ? ">MyRec" : " MyRec";
            for (i = 0; name[i]; ++i) text[i] = name[i];
        }
        break;
    case KV_UI_CARD:
        if (!row) return kv_ui_title(v, model->unit, model->slot, model->levels,
                                     model->names[model->slot - 1], '<', out);
        count = card_controls(&recipe, controls); pairs = (count + 1) / 2;
        if (row <= pairs) {
            i = (row - 1) * 2;
            return kv_ui_compact(v, model->unit, model->slot, controls[i],
                                 i + 1 < count ? controls[i + 1] : KV_UI_NO_CONTROL,
                                 model->levels, out);
        }
        if (row == pairs + 1 && count != recipe.item_count)
            return kv_ui_value(v, model->unit, model->slot, 0, model->levels->v[0], out);
        {
            const char *name = nav->armed ? "Sure?" : "Default";
            for (i = 0; name[i]; ++i) text[i] = name[i];
        }
        break;
    case KV_UI_ITEMS:
        if (!row) return kv_ui_title(v, model->unit, model->slot, model->levels,
                                     model->names[model->slot - 1], '<', out);
        i = recipe.display[row - 1];
        return kv_ui_value(v, model->unit, model->slot, i, model->levels->v[i], out);
    case KV_UI_VALUE:
        {
            KvDataItem item;
            KvDataPoint point;
            if (kv_data_find(v, model->unit, model->slot, nav->control, &item) ||
                row >= item.point_count || kv_data_point(v, &item, item.point_count - 1u - row, &point)) return -1;
            return kv_ui_value(v, model->unit, model->slot, nav->control, point.level, out);
        }
    default: return -1;
    }
    text_copy(out, text);
    return 0;
}
int kv_ui_render(const KvDataView *v, const KvUiModel *model, const KvUiNav *nav, KvUiFrame *out)
{
    KvUiFrame result = {0};
    unsigned count, i;
    if (!out || !model || !model->names || model->applied_slot > 8 || model->applied_user > 32 ||
        !nav_valid(v, model->unit, model->slot, model->levels, nav)) return -1;
    count = kv_ui_count(v, model->unit, model->slot, nav->screen, nav->control);
    if (kv_ui_layout(count, nav->current[nav->screen], nav->top[nav->screen], &result)) return -1;
    for (i = 0; i < KV_UI_PHYSICAL; ++i) {
        unsigned row = result.top + i;
        if (row < count) {
            if (logical_text(v, model, nav, row, result.text[i])) return -1;
            result.selectable |= (uint8_t)(1u << i);
        } else result.text[i][0] = ' ';
    }
    *out = result;
    return 0;
}
int kv_ui_native_disp(const KvDataView *v, unsigned unit, unsigned slot,
                      const UvLevels *levels, const KvUiNav *nav, unsigned physical,
                      UvLevels *out_levels, KvUiNav *out_nav, KvUiEvent *out_event)
{
    KvUiWindow window;
    KvUiEvent event = {KV_UI_EVENT_NONE, 0};
    unsigned count;
    if (!out_levels || !out_nav || !out_event || physical >= KV_UI_PHYSICAL ||
        !nav_valid(v, unit, slot, levels, nav)) return -1;
    count = kv_ui_count(v, unit, slot, nav->screen, nav->control);
    if (kv_ui_window(count, nav->current[nav->screen], nav->top[nav->screen], &window)) return -1;
    if (window.top + physical >= count) {
        *out_levels = *levels; *out_nav = *nav; *out_event = event;
        return 0;
    }
    if (physical != window.cursor) return -1;
    return kv_ui_disp(v, unit, slot, levels, nav, out_levels, out_nav, out_event);
}
int kv_ui_move(const KvDataView *v, unsigned unit, unsigned slot,
               const UvLevels *levels, const KvUiNav *nav, int delta,
               UvLevels *out_levels, KvUiNav *out_nav)
{
    UvLevels result;
    KvUiNav next;
    KvUiWindow window;
    unsigned count;
    int target;
    if (!out_levels || !out_nav || delta < -7 || delta > 7 || !nav_valid(v, unit, slot, levels, nav)) return -1;
    result = *levels; next = *nav; next.armed = 0;
    count = kv_ui_count(v, unit, slot, nav->screen, nav->control);
    target = (int)nav->current[nav->screen] + delta;
    if (target < 0) target = 0;
    if ((unsigned)target >= count) target = (int)count - 1;
    next.current[next.screen] = (uint8_t)target;
    if (next.screen == KV_UI_VALUE) {
        KvDataItem item;
        KvDataPoint point;
        if (kv_data_find(v, unit, slot, next.control, &item) ||
            kv_data_point(v, &item, item.point_count - 1u - (unsigned)target, &point)) return -1;
        result.v[next.control] = point.level;
    }
    if (kv_ui_window(count, (unsigned)target, next.top[next.screen], &window)) return -1;
    next.top[next.screen] = window.top;
    *out_levels = result; *out_nav = next;
    return 0;
}
int kv_ui_native_move(const KvDataView *v, unsigned unit, unsigned slot,
                      const UvLevels *levels, const KvUiNav *nav, unsigned physical,
                      UvLevels *out_levels, KvUiNav *out_nav)
{
    KvUiWindow window;
    unsigned count;
    int delta;
    if (physical >= KV_UI_PHYSICAL || !nav_valid(v, unit, slot, levels, nav)) return -1;
    count = kv_ui_count(v, unit, slot, nav->screen, nav->control);
    if (kv_ui_window(count, nav->current[nav->screen], nav->top[nav->screen], &window)) return -1;
    if (physical == (window.cursor + 1u) % 8u) delta = 1;
    else if (physical == (window.cursor + 7u) % 8u) delta = -1;
    else if (count < 8 && physical >= count) delta = 0;
    else delta = (int)physical - window.cursor;
    return kv_ui_move(v, unit, slot, levels, nav, delta, out_levels, out_nav);
}
static int open_value(const KvDataView *v, unsigned unit, unsigned slot,
                       const UvLevels *levels, unsigned control, KvUiNav *nav)
{
    unsigned current;
    KvUiWindow window;
    if (kv_ui_value_cursor(v, unit, slot, control, levels->v[control], &current)) return -1;
    nav->value_origin = nav->screen; nav->screen = KV_UI_VALUE; nav->control = (uint8_t)control;
    nav->current[KV_UI_VALUE] = (uint8_t)current;
    if (kv_ui_window(kv_ui_count(v, unit, slot, KV_UI_VALUE, control), current,
                     nav->top[KV_UI_VALUE], &window)) return -1;
    nav->top[KV_UI_VALUE] = window.top;
    return 0;
}
int kv_ui_disp(const KvDataView *v, unsigned unit, unsigned slot,
               const UvLevels *levels, const KvUiNav *nav, UvLevels *out_levels,
               KvUiNav *out_nav, KvUiEvent *out_event)
{
    UvLevels result;
    KvUiNav next;
    KvUiEvent event = {KV_UI_EVENT_NONE, 0};
    KvDataRecipe recipe;
    uint8_t controls[9];
    unsigned row, count, pairs, i;
    if (!out_levels || !out_nav || !out_event || !nav_valid(v, unit, slot, levels, nav) ||
        kv_data_recipe(v, unit, slot, &recipe)) return -1;
    result = *levels; next = *nav; row = next.current[next.screen];
    switch (next.screen) {
    case KV_UI_L1:
        event.kind = row == 9 ? KV_UI_EVENT_MYREC : KV_UI_EVENT_RECIPE;
        event.slot = (uint8_t)(row < 8 ? row + 1 : slot);
        break;
    case KV_UI_CARD:
        count = card_controls(&recipe, controls); pairs = (count + 1) / 2;
        if (!row) { next.screen = KV_UI_L1; next.armed = 0; }
        else if (row <= pairs) {
            unsigned control = controls[2 * (row - 1)];
            next.armed = 0;
            if (2 * row > count) {
                if (open_value(v, unit, slot, levels, control, &next)) return -1;
            } else {
                next.screen = KV_UI_ITEMS;
                for (i = 0; i < recipe.item_count && recipe.display[i] != control; ++i) {}
                next.current[KV_UI_ITEMS] = (uint8_t)(i + 1);
            }
        } else if (row == pairs + 1 && count != recipe.item_count) {
            next.armed = 0;
            if (open_value(v, unit, slot, levels, 0, &next)) return -1;
        } else if (!next.armed) next.armed = 1;
        else {
            if (kv_ui_default(v, unit, slot, &result)) return -1;
            next.armed = 0; event.kind = KV_UI_EVENT_DEFAULT; event.slot = (uint8_t)slot;
        }
        break;
    case KV_UI_ITEMS:
        if (!row) next.screen = KV_UI_CARD;
        else if (open_value(v, unit, slot, levels, recipe.display[row - 1], &next)) return -1;
        break;
    case KV_UI_VALUE: next.screen = next.value_origin; break;
    default: return -1;
    }
    {
        KvUiWindow window;
        count = kv_ui_count(v, unit, slot, next.screen, next.control);
        if (kv_ui_window(count, next.current[next.screen], next.top[next.screen], &window)) return -1;
        next.top[next.screen] = window.top;
    }
    *out_levels = result; *out_nav = next; *out_event = event;
    return 0;
}
int kv_ui_legacy_levels(const int8_t old[11], UvLevels *out)
{
    static const uint8_t controls[4] = {1,2,3,5};
    UvLevels result = {{100,0,0,0,0,0,0,0,0,0}};
    unsigned i;
    if (!old || !out) return -1;
    for (i = 4; i < KV_UI_LEGACY_PARAMS; ++i) if (old[i]) return -1;
    for (i = 0; i < 4; ++i) result.v[controls[i]] = old[i];
    *out = result;
    return 0;
}
int kv_ui_legacy_record(const uint8_t *record, size_t length, unsigned *slot, UvLevels *out)
{
    static const char groups[8][4] = {"GRP","GRN","HCB","STD","FCC","FCN","LCH","LVI"};
    UvLevels result;
    int8_t old[11];
    unsigned i, ordinal, changed = 0, selected;
    if (!record || !slot || !out || length != KV_UI_LEGACY_RECORD) return -1;
    selected = record[0]; ordinal = (unsigned)record[22] * 256u + record[23];
    if (selected < 1 || selected > 8 || record[1] || record[9] || record[21] ||
        ordinal < 1 || ordinal > 32) return -1;
    for (i = 0; i < 3; ++i) if (record[2 + i] != (uint8_t)groups[selected - 1][i]) return -1;
    for (i = 0; i < 11; ++i) {
        unsigned n = record[10 + i];
        old[i] = (int8_t)(n <= 127 ? (int)n : (int)n - 256);
        if (i < 4 && old[i]) changed = 1;
    }
    if (record[5] != (changed ? '*' : '-') || record[6] != '0' + ordinal / 100 ||
        record[7] != '0' + ordinal / 10 % 10 || record[8] != '0' + ordinal % 10 ||
        kv_ui_legacy_levels(old, &result)) return -1;
    *out = result; *slot = selected;
    return 0;
}
int kv_ui_entry(const uint8_t record[24], int applied, int adjusted, char out[9])
{
    UvLevels levels;
    unsigned slot, i;
    char text[9] = {0};
    if (!out || applied < 0 || applied > 1 || adjusted < 0 || adjusted > 1 ||
        kv_ui_legacy_record(record, KV_UI_LEGACY_RECORD, &slot, &levels)) return -1;
    text[0] = applied ? '>' : ' ';
    for (i = 0; i < 7; ++i) text[1 + i] = (char)record[2 + i];
    text[4] = adjusted ? '*' : '-';
    text_copy(out, text);
    return 0;
}
