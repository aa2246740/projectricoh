#include "recipe_fw.h"

static const uint8_t *const number_labels[16] = {
    rfw_defaults[0].name,rfw_defaults[1].name,rfw_defaults[2].name,rfw_defaults[3].name,
    rfw_defaults[4].name,rfw_defaults[5].name,rfw_defaults[6].name,rfw_defaults[7].name,
    rfw_defaults[8].name,rfw_defaults[9].name,rfw_defaults[10].name,rfw_defaults[11].name,
    rfw_defaults[12].name,rfw_defaults[13].name,rfw_defaults[14].name,rfw_defaults[15].name
};
#define NUMBER_REFS \
    &number_labels[0],&number_labels[1],&number_labels[2],&number_labels[3], \
    &number_labels[4],&number_labels[5],&number_labels[6],&number_labels[7], \
    &number_labels[8],&number_labels[9],&number_labels[10],&number_labels[11], \
    &number_labels[12],&number_labels[13],&number_labels[14],&number_labels[15]
/* Distinct addresses record open/closed even if heap allocation fails. */
const RfwLabelRef rfw_closed_table[16] = { NUMBER_REFS };
const RfwLabelRef rfw_empty_table[16] = { NUMBER_REFS };
const uint32_t rfw_no_details[16][3] = {{0}};

static RfwCache *current(void)
{
    RfwLabelTable table = *rfw_binding();
    uintptr_t address = (uintptr_t)table;
    uintptr_t begin, end;
    RfwCache *cache;
    if (table == rfw_closed_table || table == rfw_empty_table) return NULL;
    begin = rfw_heap_begin(); end = rfw_heap_end();
    if (begin == 0 || address % _Alignof(RfwCache) != 0 ||
        address < begin || address >= end || sizeof(*cache) > end - address) return NULL;
    cache = (RfwCache *)address;
    if (cache->table[0] != &cache->labels[0]) return NULL;
    return cache;
}

uint32_t rfw_is_open(void)
{
    RfwCache *cache = current();
    return cache != NULL ? cache->opened : *rfw_binding() == rfw_empty_table;
}

uint32_t rfw_is_active(void)
{
    /* Type 5 is patched to 16 rows even when loading failed or was closed
     * reentrantly. Never send those cursors to the native seven-mode setter. */
    return rfw_ui_active();
}

void rfw_close(void)
{
    RfwCache *cache = current();
    if (cache != NULL) cache->opened = 0;
    else *rfw_binding() = rfw_closed_table;
}

/* The UI is read-only. A fully validated bank remains usable if opening its
 * companion fails. Do not normalize that error to EMPTY or use this policy
 * for saving. The unmodified v1 save API keeps its stricter scan contract. */
static Rv1Status load_view(RfwCache *cache)
{
    uint32_t generation[2] = {0,0}, crc[2] = {0,0}, delta, reloaded;
    Rv1Status status[2], result;
    size_t actual;
    unsigned i, selected;
    for (i = 0; i < 2; ++i) {
        status[i] = rfw_read_file(NULL, rv1_bank_paths[i], cache->scratch,
                                 RV1_FILE_BYTES, &actual);
        if (status[i] == RV1_OK)
            status[i] = rv1_decode(cache->scratch, actual, NULL, &generation[i]);
        if (status[i] == RV1_OK) crc[i] = rv1_crc32(cache->scratch, RV1_FILE_BYTES);
        if (status[i] == RV1_VERSION || status[i] == RV1_NO_CARD) return status[i];
    }
    if (status[0] != RV1_OK && status[1] != RV1_OK)
        return status[0] == RV1_IO && status[1] == RV1_IO ? RV1_IO : RV1_CORRUPT;
    selected = status[0] == RV1_OK ? 0u : 1u;
    if (status[0] == RV1_OK && status[1] == RV1_OK) {
        delta = generation[1] - generation[0];
        if (delta == 0x80000000u || (delta == 0 && crc[0] != crc[1]))
            return RV1_CONFLICT;
        if (delta != 0 && delta < 0x80000000u) selected = 1;
    }
    result = rfw_read_file(NULL, rv1_bank_paths[selected], cache->scratch,
                           RV1_FILE_BYTES, &actual);
    if (result != RV1_OK) return result;
    result = rv1_decode(cache->scratch, actual, NULL, &reloaded);
    if (result != RV1_OK) return result;
    if (reloaded != generation[selected] ||
        rv1_crc32(cache->scratch, RV1_FILE_BYTES) != crc[selected]) return RV1_CONFLICT;
    return rv1_decode(cache->scratch, actual, &cache->bank, NULL);
}

static int printable(const Rv1Recipe *recipe)
{
    unsigned i;
    int visible = 0;
    for (i = 0; i < recipe->name_length; ++i) {
        if (recipe->name[i] < 32 || recipe->name[i] > 126) return 0;
        if (recipe->name[i] != 32) visible = 1;
    }
    return visible;
}

static uint32_t matching_slot(const RfwCache *cache)
{
    Rv1WritePlan plan;
    volatile uint8_t *s = rfw_settings();
    unsigned i, j;
    if (s == NULL || *rfw_word(0x200c0db0) < RV1_SETTINGS_MIN_BYTES) return 0;
    for (i = 0; i < 16; ++i) {
        const Rv1Recipe *recipe = &cache->bank.slots[i].recipe;
        if (!cache->bank.slots[i].occupied || rv1_plan(recipe, &plan) != RV1_OK) continue;
        if (cache->deep.uncertain || rfw_deep_id(recipe) != cache->deep.active) continue;
        for (j = 0; j < plan.count; ++j)
            if (s[plan.writes[j].offset] != plan.writes[j].value) break;
        if (j == plan.count) return i + 1;
    }
    return 0;
}

uint32_t rfw_open(void)
{
    RfwCache *cache = current();
    char name[33];
    unsigned i, j;
    uint32_t language, matched;
    if (cache != NULL && cache->busy) return *rfw_byte(0x2022f726);
    if (cache == NULL) {
        *rfw_binding() = rfw_empty_table;
        cache = gxr_alloc((uint32_t)sizeof(*cache));
        if (cache == NULL) return 1;
        for (i = 0; i < sizeof(*cache); ++i) ((uint8_t *)cache)[i] = 0;
        for (i = 0; i < 16; ++i) {
            cache->labels[i] = number_labels[i];
            cache->table[i] = &cache->labels[i];
        }
        *rfw_binding() = cache->table;
    }
    /* Publish the owned cache before file/preview callbacks can reenter.
     * Reuse it without freeing addresses retained by native drawing. */
    cache->busy = 1;
    cache->opened = 1;
    cache->applied_slot = 0;
    cache->last_status = RV1_EMPTY;
    cache->load_status = RV1_EMPTY;
    rv1_bank_init(&cache->bank);
    cache->load_status = load_view(cache);
    /* An unavailable card/both IO failures use compiled Canonical defaults.
     * Recognized corrupt, future or conflicting banks remain non-applicable.
     * The old loaded bank is always discarded before this decision. */
    if (cache->load_status == RV1_IO || cache->load_status == RV1_NO_CARD) {
        for (i = 0; i < 16; ++i) {
            cache->bank.slots[i].occupied = 1;
            for (j = 0; j < sizeof(Rv1Recipe); ++j)
                ((uint8_t *)&cache->bank.slots[i].recipe)[j] =
                    ((const uint8_t *)&rfw_defaults[i])[j];
        }
        cache->load_status = RV1_OK;
    }
    language = gxr_language();
    for (i = 0; i < 16; ++i) {
        const Rv1Recipe *recipe = &cache->bank.slots[i].recipe;
        cache->labels[i] = number_labels[i];
        if (cache->load_status != RV1_OK || !cache->bank.slots[i].occupied ||
            !printable(recipe)) continue;
        for (j = 0; j < recipe->name_length; ++j) name[j] = (char)recipe->name[j];
        name[j] = 0;
        cache->glyphs[i][0] = 0;
        gxr_ascii(name, recipe->name_length, cache->glyphs[i], language);
        if (cache->glyphs[i][0] != 0) cache->labels[i] = cache->glyphs[i];
    }
    matched = cache->load_status == RV1_OK ? matching_slot(cache) : 0;
    cache->applied_slot = (uint8_t)matched;
    cache->busy = 0;
    return matched != 0 ? matched : 1;
}

Rv1Status rfw_select(uint32_t slot)
{
    RfwCache *cache = current();
    Rv1Status status;
    Rv1SettingsPort port;
    if (!rfw_is_open()) return RV1_ARGUMENT;
    if (slot < 1 || slot > 16) return RV1_RANGE;
    if (cache != NULL && cache->busy) return RV1_CONFLICT;
    *rfw_byte(0x2022f726) = (uint8_t)slot;
    if (cache == NULL || cache->load_status != RV1_OK) return RV1_EMPTY;
    if (!cache->bank.slots[slot - 1].occupied) return RV1_EMPTY;
    port.context = cache;
    port.acquire = rfw_acquire;
    port.request_preview = rfw_request_preview;
    port.release = rfw_release;
    cache->pending_slot = (uint8_t)slot;
    status = rv1_apply(&port, &cache->bank.slots[slot - 1].recipe);
    cache->pending_slot = 0;
    cache->last_status = status;
    if (status == RV1_OK || status == RV1_IO) cache->applied_slot = (uint8_t)slot;
    return status;
}

uint32_t rfw_cursor_commit(void)
{
    if (!rfw_is_active()) return 0;
    (void)rfw_select(*rfw_byte(0x2022f726));
    return 1;
}

uint32_t rfw_apply_action(uint32_t keep_open)
{
    RfwCache *cache = current();
    uint32_t slot = *rfw_byte(0x2022f726);
    /* Some native routes call only overlay apply. Both routes use the same
     * selection function; a second callback for that row emits no preview. */
    if (rfw_is_active() && cache != NULL && cache->applied_slot != slot)
        (void)rfw_select(slot);
    *rfw_word(0x2037f3bc) = 0;
    if (keep_open == 0) {
        (void)gxr_layer_action(2, 1, 0);
        rfw_close();
    }
    return 1; /* Original Setting1 entry in 0x2037f46a[6]. */
}

