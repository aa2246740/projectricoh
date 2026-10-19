#include "recipe_fw.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define CHECK(x) do { if (!(x)) { fprintf(stderr,"%s:%d: %s\n",__FILE__,__LINE__,#x); exit(1); } } while (0)
static RfwLabelTable binding;
static uint32_t ready = 1, readonly, settings_length = 4096, overlay_word;
static uint32_t native_activity = 8;
static uint8_t cursor = 1, settings_a[4096], settings_b[4096];
static uint8_t *settings_pointer = settings_a;
static struct { uint8_t bytes[1120]; size_t length, position; int exists; } files[2];
static int live_handle = -1, writing, reads, opens, closes, previews, allocations, frees;
static int fail_alloc, fail_read, fail_write, fail_close, fail_create, fail_delete;
static int preview_error, reenter_preview, close_during_preview;
static int reenter_read, close_during_read, ascii_failure;
static void *allocated_cache;
static uintptr_t heap_end_trim;
static size_t chunk = 1056;
static unsigned tests;
static uint8_t ui_active = 2, ui_count = 1;
static uint8_t ui_type = 5;
static uint8_t shooting_category;
static RfwUiEntry ui_entries[2];
static int ui_null_entries;
static void deep_before_preview(void);

volatile uint32_t *rfw_word(uint32_t address)
{
    switch (address) {
    case 0x200d8080: return &ready;
    case 0x200d8084: return &readonly;
    case 0x200c0db0: return &settings_length;
    case 0x2037f3bc: return &overlay_word;
    case 0x205d9bf8: return &native_activity;
    default: CHECK(0); return NULL;
    }
}
volatile uint8_t *rfw_byte(uint32_t address)
{
    if (address == 0x205d9a7f) return &shooting_category;
    if (address == 0x2022f726) return &cursor;
    if (address == 0x2022f71c) return &ui_type;
    if (address == 0x205a27d4) return &ui_count;
    CHECK(address == 0x205a280f); return &ui_active;
}
volatile uint8_t *rfw_settings(void) { return settings_pointer; }
const volatile RfwUiEntry *rfw_ui_entries(void)
{ return ui_null_entries ? NULL : ui_entries; }
RfwLabelTable volatile *rfw_binding(void) { return &binding; }
uintptr_t rfw_heap_begin(void) { return (uintptr_t)allocated_cache; }
uintptr_t rfw_heap_end(void)
{ return allocated_cache == NULL ? 0 : (uintptr_t)allocated_cache + sizeof(RfwCache) - heap_end_trim; }
static int path_index(const char *path)
{
    if (strcmp(path,rv1_bank_paths[0]) == 0) return 0;
    CHECK(strcmp(path,rv1_bank_paths[1]) == 0);
    return 1;
}
int32_t gxr_open(const char *path, uint32_t flags)
{
    int i = path_index(path);
    CHECK(flags == 0); CHECK(live_handle == -1); ++opens;
    if (!files[i].exists) return -1;
    live_handle = i; writing = 0; files[i].position = 0;
    return i + 0x10;
}
int32_t gxr_create(const char *path, uint32_t flags)
{
    int i = path_index(path);
    CHECK(flags == 2); CHECK(live_handle == -1);
    if (fail_create) return -1;
    files[i].exists = 1; files[i].position = files[i].length = 0;
    live_handle = i; writing = 1;
    return i + 0x10;
}
int32_t gxr_read(int32_t handle, void *bytes, uint32_t length)
{
    size_t n;
    int i = handle - 0x10;
    CHECK(i == live_handle); CHECK(!writing); ++reads;
    if (reenter_read) {
        CHECK(rfw_open() == cursor);
        CHECK(rfw_select(cursor) == RV1_CONFLICT);
    }
    if (close_during_read) rfw_close();
    if (fail_read) return -1;
    n = files[i].length - files[i].position;
    if (n > length) n = length;
    if (n > chunk) n = chunk;
    memcpy(bytes, files[i].bytes + files[i].position, n);
    files[i].position += n;
    return (int32_t)n;
}
int32_t gxr_write(int32_t handle, const void *bytes, uint32_t length)
{
    size_t n = length;
    int i = handle - 0x10;
    CHECK(i == live_handle); CHECK(writing);
    if (fail_write) return -1;
    if (n > chunk) n = chunk;
    CHECK(files[i].position + n <= sizeof(files[i].bytes));
    memcpy(files[i].bytes + files[i].position, bytes, n);
    files[i].position += n; files[i].length = files[i].position;
    return (int32_t)n;
}
int32_t gxr_close(int32_t handle)
{
    CHECK(handle - 0x10 == live_handle); ++closes; live_handle = -1;
    return fail_close ? -1 : 0;
}
int32_t gxr_delete(const char *path)
{
    int i = path_index(path);
    CHECK(live_handle == -1);
    if (fail_delete || !files[i].exists) return -1;
    files[i].exists = 0;
    return 0;
}
int32_t gxr_mkdir(const char *path) { CHECK(path != NULL); return 0; }
void *gxr_alloc(uint32_t bytes)
{
    if (fail_alloc) return NULL;
    CHECK(allocated_cache == NULL);
    allocated_cache = malloc(bytes); CHECK(allocated_cache != NULL);
    ++allocations; return allocated_cache;
}
uint32_t gxr_language(void) { return 1; }
void gxr_ascii(const char *name, uint32_t length, uint8_t *out, uint32_t language)
{
    size_t i;
    CHECK(language == 1); CHECK(length <= 32); CHECK(name[length] == 0);
    if (ascii_failure) return;
    for (i = 0; i < length; ++i) { out[i*2] = 2; out[i*2+1] = (uint8_t)name[i]; }
    out[length*2] = 0;
}
void gxr_draw_text(uint32_t layer, const void *descriptor)
{ CHECK(layer == 2); CHECK(descriptor != NULL); }
int32_t gxr_layer_action(uint32_t part, uint32_t action, uint32_t argument)
{
    CHECK(argument == 0);
    if (part == 2 && action == 1) ui_count = 0;
    return 0;
}
int32_t gxr_preview(uint32_t argument)
{
    deep_before_preview();
    CHECK(argument == 0); ++previews;
    CHECK(settings_pointer[0x36e] == 4 || settings_pointer[0x36e] == 3 || settings_pointer[0x36e] == 6);
    if (reenter_preview) CHECK(rfw_select(cursor) == RV1_CONFLICT);
    if (close_during_preview) rfw_close();
    return preview_error ? -1 : 0;
}

static void passed(const char *name)
{ ++tests; printf("PASS %s\n",name); }
static void reset(void)
{
    CHECK(live_handle == -1);
    rfw_close();
    /* Only the test's simulated power-off tears down the resident heap. */
    if (allocated_cache != NULL) { free(allocated_cache); ++frees; allocated_cache = NULL; }
    binding = rfw_closed_table;
    heap_end_trim = 0;
    CHECK(allocations == frees);
    memset(files,0,sizeof(files));
    memset(settings_a,0xa5,sizeof(settings_a)); memset(settings_b,0x5a,sizeof(settings_b));
    settings_pointer = settings_a; settings_length = 4096;
    shooting_category = 0;
    ready = 1; readonly = 0; cursor = 1; ui_active = 2; ui_count = 1; ui_type = 5; ui_null_entries = 0;
    native_activity = 8;
    memset(ui_entries,0,sizeof(ui_entries));
    ui_entries[0].tag = 33; ui_entries[0].state = 0x2022f71c;
    fail_alloc = fail_read = fail_write = fail_close = fail_create = fail_delete = 0;
    preview_error = reenter_preview = close_during_preview = 0;
    reenter_read = close_during_read = ascii_failure = 0;
    previews = reads = opens = closes = 0; chunk = 1056;
}
static void make_bank(unsigned index, uint32_t generation, uint8_t value)
{
    Rv1Bank bank;
    unsigned i;
    rv1_bank_init(&bank);
    for (i = 0; i < 16; ++i) {
        Rv1Recipe *recipe;
        if (i != 0 && i != 1 && i != 15) continue;
        bank.slots[i].occupied = 1;
        recipe = &bank.slots[i].recipe;
        recipe->base_mode = RV1_BASE_COLOR;
        recipe->name_length = 5;
        memcpy(recipe->name,i == 0 ? "Amber" : i == 1 ? "Cool!" : "Green",5);
        memset(recipe->raw,value,13);
        recipe->wb[0] = -8; recipe->wb[1] = 8;
    }
    CHECK(rv1_encode(&bank,generation,files[index].bytes,1120) == RV1_OK);
    files[index].exists = 1; files[index].length = 1056;
}
static void verify_apply(uint8_t *s, const uint8_t *before, uint8_t value)
{
    uint8_t expected[4096];
    unsigned i;
    static const unsigned fields[13] = {
        0x36f,0x370,0x371,0x8ac,0x8ad,0x8ae,0x8af,0x8b0,
        0x8b1,0x8b2,0x8b3,0x8b4,0x8b5
    };
    memcpy(expected,before,4096);
    for (i = 0; i < 13; ++i) expected[fields[i]] = value;
    expected[0x36e] = 4; expected[0x6dd] = 1; expected[0x6de] = 17;
    CHECK(memcmp(s,expected,4096) == 0);
}
static void ui_tests(const char *example)
{
    uint8_t before[4096], scratch[1056];
    Rv1Bank bank;
    unsigned i;
    int read_count, allocation_count, free_count;
    RfwLabelTable retained_table;
    FILE *input;
    reset(); make_bank(0,1,3); memcpy(before,settings_a,4096);
    CHECK(rfw_open() == 1); CHECK(rfw_is_open());
    CHECK(memcmp(settings_a,before,4096) == 0); CHECK(previews == 0);
    CHECK(*binding[0] != *rfw_closed_table[0]);
    CHECK((*binding[0])[0] == 2 && (*binding[0])[1] == 'A');
    CHECK(strcmp((const char *)*binding[7],(const char *)rfw_defaults[7].name) == 0);
    CHECK(live_handle == -1);
    passed("open loads single bank and retains settings");
    read_count = reads;
    CHECK(rfw_select(1) == RV1_OK); verify_apply(settings_a,before,3);
    CHECK(previews == 1); CHECK(reads == read_count);
    passed("navigation applies 16 exact bytes before preview without SD IO");
    memcpy(before,settings_a,4096);
    for (i = 3; i <= 15; ++i) CHECK(rfw_select(i) == RV1_EMPTY);
    CHECK(cursor == 15); CHECK(previews == 1); CHECK(memcmp(settings_a,before,4096) == 0);
    CHECK(rfw_select(16) == RV1_OK); CHECK(cursor == 16); CHECK(previews == 2);
    CHECK(rfw_select(0) == RV1_RANGE && rfw_select(17) == RV1_RANGE);
    passed("all 16 rows including 8 9 10 15 16 and empty slots");
    CHECK(rfw_apply_action(1) == 1 && rfw_is_open()); CHECK(previews == 2);
    CHECK(rfw_apply_action(0) == 1 && !rfw_is_open()); CHECK(previews == 2);
    CHECK(allocations == frees + 1); CHECK(memcmp(settings_a,before,4096) == 0);
    passed("MENU OK close preserves current recipe and resident cache");
    ui_count = 1;
    make_bank(0,2,8); CHECK(rfw_open() == 1); CHECK(rfw_select(2) == RV1_OK);
    memcpy(before,settings_a,4096); rfw_close(); CHECK(rfw_open() == 1);
    CHECK(memcmp(settings_a,before,4096) == 0); CHECK(allocations == frees + 1);
    passed("reopen reloads SD and reconstructs first matching row");
    settings_pointer = settings_b; memcpy(before,settings_b,4096);
    CHECK(rfw_select(16) == RV1_OK); verify_apply(settings_b,before,8);
    passed("every apply resolves replacement S pointer");
    preview_error = 1; CHECK(rfw_select(1) == RV1_IO); CHECK(((RfwCache *)(uintptr_t)binding)->busy == 0);
    passed("preview failure retains complete recipe and releases ownership");
    preview_error = 0; reenter_preview = 1; CHECK(rfw_select(1) == RV1_OK);
    passed("same task reentrant apply is rejected");
    reenter_preview = 0; close_during_preview = 1; CHECK(rfw_select(1) == RV1_OK);
    CHECK(!rfw_is_open() && allocations == frees + 1);
    passed("close during preview clears open state without freeing native label addresses");
    reset(); CHECK(rfw_open() == 1);
    for (i = 1; i <= 16; ++i) {
        CHECK(memcmp(&((RfwCache *)allocated_cache)->bank.slots[i-1].recipe,
                     &rfw_defaults[i-1],sizeof(Rv1Recipe)) == 0);
        CHECK((*binding[i-1])[0] == 2);
    }
    CHECK(previews == 0); passed("no files opens all compiled Canonical names without applying settings");
    reset(); make_bank(0,1,3); files[0].bytes[80] ^= 1;
    memcpy(before,settings_a,4096); CHECK(rfw_open() == 1);
    CHECK(rfw_select(1) == RV1_EMPTY && previews == 0); CHECK(memcmp(before,settings_a,4096) == 0);
    passed("corrupt bank shows numbers and cannot apply");
    reset(); make_bank(0,1,3); make_bank(1,2,8); files[1].bytes[80] ^= 1;
    CHECK(rfw_open() == 1); CHECK(rfw_select(1) == RV1_OK); CHECK(settings_a[0x36f] == 3);
    passed("corrupt newer bank falls back to fully valid old bank");
    reset(); make_bank(0,1,3); make_bank(1,2,8);
    CHECK(rfw_open() == 1); CHECK(rfw_select(16) == RV1_OK); CHECK(settings_a[0x36f] == 8);
    passed("newest valid bank selected");
    reset(); make_bank(0,1,3); make_bank(1,1,8);
    CHECK(rfw_open() == 1 && rfw_select(1) == RV1_EMPTY); CHECK(previews == 0);
    passed("equal generation conflict cannot apply");
    reset(); make_bank(0,0xffffffffu,3); make_bank(1,0,8);
    CHECK(rfw_open() == 1 && rfw_select(1) == RV1_OK); CHECK(settings_a[0x36f] == 8);
    passed("generation wraps correctly");
    reset(); make_bank(0,0,3); make_bank(1,0x80000000u,8);
    CHECK(rfw_open() == 1 && rfw_select(1) == RV1_EMPTY);
    passed("half-space generation conflict cannot apply");
    reset(); make_bank(0,1,3);
    CHECK(rv1_decode(files[0].bytes,1056,&bank,NULL) == RV1_OK);
    bank.slots[0].recipe.name[0] = 0xff;
    CHECK(rv1_encode(&bank,1,scratch,1056) == RV1_RANGE);
    passed("non ASCII v2 names are rejected before encoding");
    reset(); fail_alloc = 1; CHECK(rfw_open() == 1 && rfw_is_open());
    CHECK(rfw_select(16) == RV1_EMPTY); rfw_apply_action(0); CHECK(!rfw_is_open());
    passed("heap failure still opens 16 numbered rows");
    reset(); ready = 0; CHECK(rfw_open() == 1 && rfw_select(4) == RV1_OK); CHECK(opens == 0);
    passed("no card opens and applies compiled native Canonical defaults without file handles");
    reset(); make_bank(0,1,3); CHECK(rfw_open() == 1);
    settings_length = 0x8b5; memcpy(before,settings_a,4096);
    CHECK(rfw_select(1) == RV1_LENGTH); CHECK(previews == 0 && memcmp(before,settings_a,4096) == 0);
    settings_length = 4096; settings_pointer = NULL; CHECK(rfw_select(1) == RV1_LENGTH);
    passed("short or null S is never written");
    reset(); make_bank(0,1,3);
    allocation_count = allocations; free_count = frees;
    CHECK(rfw_open() == 1); retained_table = binding;
    for (i = 0; i < 100; ++i) {
        CHECK(rfw_open() == 1); CHECK(binding == retained_table);
        rfw_close(); CHECK(!rfw_is_open());
        CHECK((*retained_table[0])[1] == 'A');
    }
    CHECK(allocations == allocation_count + 1 && frees == free_count && live_handle == -1);
    CHECK(rfw_cursor_commit() == 1 && previews == 0);
    passed("100 open close cycles reuse one allocation and closed cache cannot reach seven-mode setter");
    reset(); input = fopen(example,"rb"); CHECK(input != NULL);
    CHECK(fread(scratch,1,sizeof(scratch),input) == 1056); CHECK(fgetc(input) == EOF); CHECK(fclose(input) == 0);
    CHECK(rv1_decode(scratch,1056,&bank,NULL) == RV1_OK);
    CHECK(bank.slots[0].recipe.raw[0] == 4 && bank.slots[1].recipe.raw[0] == 8);
    CHECK(bank.slots[15].recipe.wb[0] == -3 && !bank.slots[3].occupied);
    memcpy(files[0].bytes,scratch,1056); files[0].exists = 1; files[0].length = 1056;
    CHECK(rfw_open() == 1 && rfw_select(16) == RV1_OK);
    CHECK(settings_a[0x6dd] == 6 && settings_a[0x6de] == 10);
    passed("Python example decodes with unmodified C v1 and applies slot16");
    reset(); make_bank(0,1,3); CHECK(rfw_open() == 1);
    cursor = 1; CHECK(rfw_apply_action(0) == 1);
    CHECK(settings_a[0x36f] == 3 && previews == 1 && !rfw_is_open());
    passed("OK selects initial highlighted recipe without cursor movement");
    reset(); make_bank(0,1,3); CHECK(rfw_open() == 1);
    cursor = 16; CHECK(rfw_apply_action(1) == 1 && previews == 1);
    CHECK(rfw_apply_action(1) == 1 && previews == 1);
    CHECK(rfw_cursor_commit() == 1 && previews == 2);
    passed("overlay only selection route applies and duplicate overlay is deduplicated");
    ui_active = 0; memcpy(before,settings_a,4096); read_count = previews;
    CHECK(rfw_is_open() && !rfw_is_active());
    cursor = 2; CHECK(rfw_cursor_commit() == 0);
    CHECK(previews == read_count && memcmp(before,settings_a,4096) == 0);
    passed("native main menu resumes original branch while recipe cache still exists");
    ui_active = 2; ui_entries[0].tag = 9; CHECK(!rfw_is_active());
    ui_entries[0].tag = 33; ui_entries[0].state = 0x2022db60; CHECK(!rfw_is_active());
    ui_entries[0].state = 0x2022f71c; ui_count = 0; CHECK(!rfw_is_active());
    ui_count = 3; CHECK(!rfw_is_active());
    ui_count = 1; ui_null_entries = 1; CHECK(!rfw_is_active());
    ui_null_entries = 0; ui_count = 2;
    ui_entries[1].tag = 33; ui_entries[1].state = 0x2022f71c; CHECK(rfw_is_active());
    ui_entries[1].tag = 9; CHECK(!rfw_is_active());
    passed("actual UI predicate checks active part top tag state count and null entries");
    reset(); make_bank(0,1,3); CHECK(rfw_open() == 1);
    ui_active = 1; cursor = 1; memcpy(before,settings_a,4096);
    overlay_word = 32;
    CHECK(!rfw_is_active() && rfw_cursor_commit() == 0);
    CHECK(rfw_is_open() && overlay_word == 32 && ui_count == 1);
    CHECK(previews == 0 && memcmp(before,settings_a,4096) == 0);
    passed("main menu is left for native handling without changing overlay or cache");
    reset(); make_bank(0,1,3); CHECK(rfw_open() == 1);
    memcpy(before,settings_a,4096); cursor = 16;
    for (i = 0; i < 256; ++i) {
        if (i == 5) continue;
        ui_type = (uint8_t)i;
        CHECK(!rfw_is_active());
        CHECK(rfw_cursor_commit() == 0);
        CHECK(previews == 0 && memcmp(before,settings_a,4096) == 0);
    }
    ui_type = 5; CHECK(rfw_is_active());
    passed("all other ADJ list types bypass recipe commit despite shared layer state");
    reset(); make_bank(0,1,3); CHECK(rfw_open() == 1);
    retained_table = binding; memcpy(before,settings_a,4096);
    CHECK(gxr_layer_action(2,1,0) == 0);
    CHECK(rfw_is_open() && !rfw_is_active());
    cursor = 16; CHECK(rfw_cursor_commit() == 0);
    CHECK(previews == 0 && memcmp(before,settings_a,4096) == 0);
    CHECK(binding == retained_table && (*retained_table[0])[1] == 'A');
    ui_count = 1; make_bank(0,2,8); CHECK(rfw_open() == 1);
    CHECK(binding == retained_table && rfw_select(16) == RV1_OK);
    CHECK(settings_a[0x36f] == 8);
    passed("unhooked native close blocks commits and reopen reloads the resident cache");
    reset(); make_bank(0,1,3); CHECK(rfw_open() == 1);
    retained_table = binding; allocation_count = allocations;
    rfw_close(); ready = 0; memcpy(before,settings_a,4096);
    CHECK(rfw_open() == 1);
    CHECK(((RfwCache *)allocated_cache)->load_status == RV1_OK);
    CHECK(binding == retained_table && allocations == allocation_count);
    CHECK(memcmp(&((RfwCache *)allocated_cache)->bank.slots[0].recipe,&rfw_defaults[0],sizeof(Rv1Recipe)) == 0);
    CHECK(memcmp(before,settings_a,4096) == 0 && previews == 0);
    ready = 1; make_bank(0,2,8); CHECK(rfw_open() == 1);
    CHECK(rfw_select(1) == RV1_OK && settings_a[0x36f] == 8);
    passed("removed card replaces the old bank with compiled defaults and a replacement card reloads");
    reset(); make_bank(0,1,3); CHECK(rfw_open() == 1);
    files[0].bytes[80] ^= 1; memcpy(before,settings_a,4096);
    CHECK(rfw_open() == 1 && rfw_select(1) == RV1_EMPTY);
    CHECK(strcmp((const char *)*binding[0],(const char *)rfw_defaults[0].name) == 0);
    CHECK(memcmp(before,settings_a,4096) == 0 && previews == 0);
    passed("corruption on reopen cannot use the previous valid bank");
    reset(); make_bank(0,1,3); CHECK(rfw_open() == 1);
    ascii_failure = 1; CHECK(rfw_open() == 1);
    CHECK(strcmp((const char *)*binding[0],(const char *)rfw_defaults[0].name) == 0);
    CHECK(rfw_select(1) == RV1_OK);
    passed("failed glyph conversion on reuse cannot display an old name");
    reset(); make_bank(0,1,3); reenter_read = 1;
    allocation_count = allocations; CHECK(rfw_open() == 1);
    CHECK(allocations == allocation_count + 1 && previews == 0 && live_handle == -1);
    CHECK(rfw_select(1) == RV1_OK);
    passed("file callback reentry cannot allocate again or apply an incomplete bank");
    reset(); make_bank(0,1,3); close_during_read = 1;
    CHECK(rfw_open() == 1 && !rfw_is_open());
    CHECK(rfw_select(1) == RV1_ARGUMENT && previews == 0);
    cursor = 16; CHECK(rfw_is_active() && rfw_cursor_commit() == 1);
    CHECK(previews == 0);
    CHECK(live_handle == -1);
    close_during_read = 0; CHECK(rfw_open() == 1 && rfw_is_open());
    passed("close during loading leaves visible 16-row UI intercepted without applying stale data");
    reset(); make_bank(0,1,3); fail_alloc = 1;
    CHECK(rfw_open() == 1 && binding == rfw_empty_table);
    rfw_close(); fail_alloc = 0; CHECK(rfw_open() == 1);
    CHECK(rfw_select(1) == RV1_OK && settings_a[0x36f] == 3);
    passed("allocation failure can recover on the next open");
    {
        const uintptr_t invalid[] = {0,1,UINT32_C(0x2022d610),UINTPTR_MAX};
        for (i = 0; i < sizeof(invalid)/sizeof(invalid[0]); ++i) {
            reset(); binding = (RfwLabelTable)invalid[i];
            CHECK(!rfw_is_open()); rfw_close();
            CHECK(binding == rfw_closed_table);
            make_bank(0,1,3); CHECK(rfw_open() == 1);
            CHECK(rfw_select(1) == RV1_OK);
        }
    }
    passed("null misaligned and original-ROM table pointers are rejected before dereference");
    {
        RfwCache saved;
        RfwCache *cache;
        reset(); make_bank(0,1,3); CHECK(rfw_open() == 1);
        cache = allocated_cache; saved = *cache;
        binding = (RfwLabelTable)((uintptr_t)cache + 1);
        CHECK(!rfw_is_open()); rfw_close();
        CHECK(memcmp(cache,&saved,sizeof(saved)) == 0);
        binding = cache->table; heap_end_trim = 1;
        CHECK(!rfw_is_open()); rfw_close();
        CHECK(memcmp(cache,&saved,sizeof(saved)) == 0);
        heap_end_trim = 0; cache->table[0] = &cache->labels[1];
        binding = cache->table; saved = *cache;
        CHECK(!rfw_is_open()); rfw_close();
        CHECK(memcmp(cache,&saved,sizeof(saved)) == 0);
    }
    passed("in-heap invalid alignment truncated extent and foreign table identity cannot be written");
}

static void full_library_test(const char *path)
{
    static const unsigned offsets[13] = {
        0x36f,0x370,0x371,0x8ac,0x8ad,0x8ae,0x8af,0x8b0,
        0x8b1,0x8b2,0x8b3,0x8b4,0x8b5
    };
    static const unsigned changed_field[12] = {0,0,0,1,1,2,2,3,4,5,6,7};
    static const uint8_t changed_value[12] = {3,6,8,6,8,6,8,8,8,8,8,8};
    uint8_t expected[4096];
    unsigned slot, field;
    FILE *input;
    reset(); input = fopen(path,"rb"); CHECK(input != NULL);
    CHECK(fread(files[0].bytes,1,sizeof(files[0].bytes),input) == 1056);
    CHECK(fgetc(input) == EOF && fclose(input) == 0);
    files[0].exists = 1; files[0].length = 1056;
    CHECK(rfw_open() == 1);
    for (slot = 1; slot <= 16; ++slot) {
        CHECK((*binding[slot-1])[0] == 2);
        memcpy(expected,settings_a,4096);
        for (field = 0; field < 13; ++field) expected[offsets[field]] = 3;
        expected[0x36e] = 4; expected[0x6dd] = expected[0x6de] = 9;
        if (slot <= 12) expected[offsets[changed_field[slot-1]]] = changed_value[slot-1];
        if (slot == 13) expected[0x6dd] = 11;
        if (slot == 14) expected[0x6dd] = 7;
        if (slot == 15) expected[0x6de] = 11;
        if (slot == 16) expected[0x6de] = 7;
        cursor = (uint8_t)slot;
        CHECK(rfw_cursor_commit() == 1);
        CHECK(memcmp(expected,settings_a,4096) == 0 && previews == (int)slot);
    }
    rfw_close(); CHECK(rfw_open() == 16 && previews == 16);
    CHECK(rfw_apply_action(0) == 1 && previews == 16);
    passed("all 16 named file recipes apply expected fields and reopen matches slot16");
    reset();
}

static void platform_tests(void)
{
    uint8_t bytes[1056], saved[1120];
    size_t actual;
    Rv1Bank bank;
    Rv1StoreInfo info;
    reset(); make_bank(0,1,3); chunk = 37;
    CHECK(rfw_read_file(NULL,rv1_bank_paths[0],bytes,1056,&actual) == RV1_OK);
    CHECK(actual == 1056 && memcmp(bytes,files[0].bytes,1056) == 0 && closes == 1);
    passed("read handles partial chunks and detects exact EOF");
    files[0].length = 1057;
    CHECK(rfw_read_file(NULL,rv1_bank_paths[0],bytes,1056,&actual) == RV1_OK && actual == 1057);
    passed("oversized file detected with one byte probe");
    files[0].length = 1055;
    CHECK(rfw_read_file(NULL,rv1_bank_paths[0],bytes,1056,&actual) == RV1_OK && actual == 1055);
    passed("short file exposes real byte count");
    fail_read = 1;
    CHECK(rfw_read_file(NULL,rv1_bank_paths[0],bytes,1056,&actual) == RV1_IO && live_handle == -1);
    passed("read error always closes handle");
    fail_read = 0; fail_close = 1;
    CHECK(rfw_read_file(NULL,rv1_bank_paths[0],bytes,1056,&actual) == RV1_IO && live_handle == -1);
    passed("read close error propagates");
    fail_close = 0;
    CHECK(rfw_read_file(NULL,rv1_bank_paths[1],bytes,1056,&actual) == RV1_IO);
    passed("unknown open error retains IO status");
    CHECK(rfw_write_file(NULL,"/ATA1/PARAM.DAT",bytes,1056,&actual) == RV1_ARGUMENT);
    passed("file adapter rejects unrelated path");
    reset(); make_bank(0,1,3); make_bank(1,1,8);
    memcpy(bytes,files[0].bytes,1056); memcpy(saved,files[0].bytes,1120); chunk = 31;
    CHECK(rfw_write_file(NULL,rv1_bank_paths[1],bytes,1056,&actual) == RV1_OK && actual == 1056);
    CHECK(memcmp(saved,files[0].bytes,1120) == 0); CHECK(memcmp(bytes,files[1].bytes,1056) == 0);
    passed("write recreates only named alternate bank and completes partial writes");
    fail_write = 1;
    CHECK(rfw_write_file(NULL,rv1_bank_paths[1],bytes,1056,&actual) == RV1_IO && live_handle == -1);
    CHECK(memcmp(saved,files[0].bytes,1120) == 0);
    passed("write failure closes handle and preserves other bank");
    fail_write = 0; fail_close = 1;
    CHECK(rfw_write_file(NULL,rv1_bank_paths[1],bytes,1056,&actual) == RV1_IO && actual == 1056 && live_handle == -1);
    passed("write close failure propagates after all bytes accepted");
    fail_close = 0; fail_delete = 1;
    CHECK(rfw_write_file(NULL,rv1_bank_paths[1],bytes,1056,&actual) == RV1_IO && actual == 0);
    passed("unknown delete error cannot authorize creation");
    fail_delete = 0; fail_create = 1;
    CHECK(rfw_write_file(NULL,rv1_bank_paths[1],bytes,1056,&actual) == RV1_IO && live_handle == -1);
    passed("create failure does not leak handle");
    readonly = 1; CHECK(rfw_write_file(NULL,rv1_bank_paths[1],bytes,1056,&actual) == RV1_READ_ONLY);
    ready = 0; CHECK(rfw_write_file(NULL,rv1_bank_paths[1],bytes,1056,&actual) == RV1_NO_CARD);
    passed("media readiness and write protection block file mutation");
    reset(); make_bank(0,1,3); make_bank(1,0,8);
    CHECK(rv1_store_load(&rfw_store,bytes,1056,&bank,&info) == RV1_OK);
    CHECK(info.bank_index == 0 && info.generation == 1 && bank.slots[0].recipe.raw[0] == 3);
    memcpy(saved,files[0].bytes,1120); bank.slots[0].recipe.raw[0] = 9;
    CHECK(rv1_store_save(&rfw_store,bytes,1056,&bank,&info) == RV1_OK);
    CHECK(info.bank_index == 1 && info.generation == 2 && memcmp(saved,files[0].bytes,1120) == 0);
    CHECK(rv1_store_load(&rfw_store,bytes,1056,&bank,&info) == RV1_OK && bank.slots[0].recipe.raw[0] == 9);
    passed("unmodified v1 load save uses real platform callbacks and alternate bank");
    reset(); rv1_bank_init(&bank);
    CHECK(rv1_store_save(&rfw_store,bytes,1056,&bank,&info) == RV1_IO);
    CHECK(!files[0].exists && !files[1].exists);
    passed("unclassified absent targets block camera side initialization");
    reset();
}

static void mixed_mode_tests(void)
{
    Rv1Bank bank;
    Rv1Recipe *r;
    uint8_t before[4096], expected[4096];
    unsigned i, tone;
    const uint8_t tones[]={6,1,2,3,4};
    reset(); make_bank(0,1,3);
    CHECK(rv1_decode(files[0].bytes,1056,&bank,NULL)==RV1_OK);
    bank.slots[3].occupied=1;r=&bank.slots[3].recipe;
    memset(r,0,sizeof(*r));r->name_length=2;memcpy(r->name,"BW",2);
    r->base_mode=3;r->raw[0]=9;r->raw[1]=4;
    bank.slots[4]=bank.slots[3];r=&bank.slots[4].recipe;
    r->base_mode=6;r->raw[0]=8;r->raw[1]=3;r->raw[2]=7;r->raw[3]=6;
    for(tone=0;tone<5;++tone) {
        bank.slots[4].recipe.raw[3]=tones[tone];
        CHECK(rv1_encode(&bank,2,files[0].bytes,1120)==RV1_OK);
        CHECK(rfw_open()>=1);
        CHECK(rfw_select(1)==RV1_OK);
        memcpy(before,settings_a,4096);memcpy(expected,before,4096);
        expected[0x645]=9;expected[0x646]=4;expected[0x6dd]=expected[0x6de]=9;expected[0x36e]=3;
        CHECK(rfw_select(4)==RV1_OK && memcmp(settings_a,expected,4096)==0);
        rfw_close();CHECK(rfw_open()==4);
        settings_a[0x36f]^=1;settings_a[0x641]^=1; /* inactive fields cannot change matching. */
        rfw_close();CHECK(rfw_open()==4);
        memcpy(expected,settings_a,4096);
        expected[0x641]=8;expected[0x642]=3;expected[0x644]=7;expected[0x643]=tones[tone];
        expected[0x36e]=6;
        CHECK(rfw_select(5)==RV1_OK && memcmp(settings_a,expected,4096)==0);
        rfw_close();CHECK(rfw_open()==5);
        settings_a[0x645]^=1;settings_a[0x8b1]^=1;
        rfw_close();CHECK(rfw_open()==5);
        settings_a[0x643]=0;rfw_close();CHECK(rfw_open()==1);
        CHECK(((RfwCache *)allocated_cache)->applied_slot==0);
        CHECK(rfw_select(16)==RV1_OK && settings_a[0x36e]==4);
    }
    passed("color BW and all five TE tones write only native fields and match on reopen");
    memcpy(before,settings_a,4096);i=(unsigned)previews;
    for(tone=1;tone<256;++tone) {
        shooting_category=(uint8_t)tone;
        CHECK(rfw_select(4)==RV1_CONFLICT);
        CHECK(memcmp(before,settings_a,4096)==0 && previews==(int)i);
        CHECK(((RfwCache *)allocated_cache)->busy==0);
    }
    shooting_category=0;
    ui_active=0;CHECK(rfw_select(4)==RV1_CONFLICT);
    CHECK(memcmp(before,settings_a,4096)==0 && previews==(int)i);
    passed("nonordinary shooting categories and inactive native ADJ block writes and previews");
    reset();
}

#include "test_deep.inc"

static void isolated_activity_tests(void)
{
    uint8_t before[4096];
    unsigned activity;
    int preview_count;
    reset(); make_bank(0,1,3); CHECK(rfw_open() == 1);
    memcpy(before,settings_a,sizeof(before)); preview_count = previews;
    /* Native left/right can publish the new ADJ function before its overlay
     * replaces the old type-5 state. A retained recipe cache is not ownership. */
    for (activity = 0; activity <= 23; ++activity) {
        if (activity == 8) continue;
        native_activity = activity;
        CHECK(rfw_is_active() == 0);
        CHECK(rfw_select(1) == RV1_CONFLICT);
        CHECK(previews == preview_count && memcmp(before,settings_a,sizeof(before)) == 0);
    }
    native_activity = UINT32_MAX; CHECK(rfw_is_active() == 0);
    CHECK(rfw_select(1) == RV1_CONFLICT);
    native_activity = 8;
    CHECK(rfw_is_active() == 1 && rfw_select(1) == RV1_OK);
    passed("only native Image Settings owns the recipe UI while stale overlays survive ADJ function switches");
    reset(); make_bank(0,1,3); CHECK(rfw_open() == 1);
    memcpy(before, settings_a, sizeof(before)); preview_count = previews;
    native_activity = 6; ui_type = 3; cursor = 4;
    CHECK(rfw_is_active() == 0 && rfw_cursor_commit() == 0);
    native_activity = 7; ui_type = 6; cursor = 4;
    CHECK(rfw_is_active() == 0 && rfw_cursor_commit() == 0);
    native_activity = 9; ui_type = 5; cursor = 4;
    CHECK(rfw_is_active() == 0 && rfw_cursor_commit() == 0);
    native_activity = 6; ui_type = 5; cursor = 4;
    CHECK(rfw_is_active() == 0 && rfw_cursor_commit() == 0);
    CHECK(previews == preview_count && memcmp(before, settings_a, sizeof(before)) == 0);
    native_activity = 8; ui_type = 5; cursor = 1;
    CHECK(rfw_cursor_commit() == 1 && previews == preview_count + 1);
    passed("ISO type 3, activity 7 type 6 and other non-8 activities return the key");
    reset();
}

static void high_row_failure_tests(void)
{
    static const uint8_t rows[] = {8, 12, 16};
    uint8_t before[4096];
    unsigned i;
    int preview_count;
    RfwCache *cache;
    reset(); make_bank(0, 1, 3); CHECK(rfw_open() == 1);
    memcpy(before, settings_a, sizeof(before)); preview_count = previews;
    rfw_close(); CHECK(!rfw_is_open() && rfw_is_active());
    for (i = 0; i < 3; ++i) {
        cursor = rows[i];
        CHECK(rfw_select(rows[i]) == RV1_ARGUMENT);
        CHECK(rfw_cursor_commit() == 1);
    }
    CHECK(previews == preview_count && memcmp(before, settings_a, sizeof(before)) == 0);
    passed("closed cache consumes rows 8 12 and 16 without reaching the seven-mode setter");
    reset(); make_bank(0, 1, 3); CHECK(rfw_open() == 1);
    cache = (RfwCache *)allocated_cache;
    cache->busy = 1;
    memcpy(before, settings_a, sizeof(before)); preview_count = previews;
    for (i = 0; i < 3; ++i) {
        cursor = rows[i];
        CHECK(rfw_is_active() && rfw_select(rows[i]) == RV1_CONFLICT);
        CHECK(rfw_cursor_commit() == 1);
    }
    CHECK(previews == preview_count && memcmp(before, settings_a, sizeof(before)) == 0);
    cache->busy = 0;
    passed("busy cache consumes rows 8 12 and 16 without writing S or previewing");
    cache->load_status = RV1_EMPTY;
    memcpy(before, settings_a, sizeof(before)); preview_count = previews;
    for (i = 0; i < 3; ++i) {
        cursor = rows[i];
        CHECK(rfw_is_active() && rfw_select(rows[i]) == RV1_EMPTY);
        CHECK(rfw_cursor_commit() == 1);
    }
    CHECK(previews == preview_count && memcmp(before, settings_a, sizeof(before)) == 0);
    passed("empty load consumes rows 8 12 and 16 without writing S or previewing");
    reset();
}

int main(int argc, char **argv)
{
    CHECK(argc == 5); binding = rfw_closed_table;
    isolated_activity_tests();
    high_row_failure_tests();
    ui_tests(argv[1]); full_library_test(argv[2]); platform_tests(); mixed_mode_tests();
    deep_tests(argv[3]);
    legacy_canonical_test(argv[4]);
    CHECK(allocations == frees && live_handle == -1);
    printf("RESULT %u cases passed\n",tests);
    return 0;
}
