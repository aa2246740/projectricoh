#include "recipe_v1.h"
#include "fixture.h"

#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define CHECK(x) do { if (!(x)) { fprintf(stderr, "FAIL line %d: %s\n", __LINE__, #x); exit(1); } } while (0)
static unsigned cases;
static void pass(const char *name) { ++cases; printf("PASS %s\n", name); }

static void put32(uint8_t *p, uint32_t v)
{
    p[0] = (uint8_t)(v >> 24); p[1] = (uint8_t)(v >> 16);
    p[2] = (uint8_t)(v >> 8); p[3] = (uint8_t)v;
}
static void fix_crcs(uint8_t *file)
{
    unsigned i;
    for (i = 0; i < 16; ++i) {
        uint8_t *p = file + 32 + 64 * i;
        put32(p + 60, rv1_crc32(p, 60));
    }
    put32(file + 24, rv1_crc32(file + 32, 1024));
    put32(file + 28, rv1_crc32(file, 28));
}
static Rv1Recipe recipe(unsigned n)
{
    Rv1Recipe r;
    const uint8_t *raw = n == 1 ? fixture_setting1 : fixture_setting2;
    unsigned i;
    memset(&r, 0, sizeof(r));
    r.base_mode = RV1_BASE_COLOR;
    r.name_length = 3;
    r.name[0] = 'R'; r.name[1] = '0'; r.name[2] = (uint8_t)('0' + n);
    for (i = 0; i < 13; ++i) r.raw[i] = raw[i];
    r.wb[0] = fixture_wb[0]; r.wb[1] = fixture_wb[1];
    return r;
}
static void fill_bank(Rv1Bank *bank)
{
    unsigned i;
    rv1_bank_init(bank);
    for (i = 0; i < 16; ++i) {
        bank->slots[i].occupied = 1;
        bank->slots[i].recipe = recipe((i & 1u) + 1u);
    }
}
static void format_tests(const char *output)
{
    uint8_t file[RV1_FILE_BYTES + 1], good[RV1_FILE_BYTES], old[RV1_FILE_BYTES + 1];
    Rv1Bank bank, decoded, sentinel;
    unsigned i, j;
    FILE *f;
    fill_bank(&bank);
    CHECK(rv1_crc32((const uint8_t *)"123456789", 9) == UINT32_C(0xcbf43926));
    pass("crc_known_vector");
    CHECK(rv1_encode(&bank, 42, file, sizeof(file)) == RV1_OK);
    CHECK(rv1_decode(file, RV1_FILE_BYTES, &decoded, NULL) == RV1_OK);
    CHECK(decoded.generation == 42);
    for (i = 0; i < 16; ++i) CHECK(memcmp(&bank.slots[i], &decoded.slots[i], sizeof(Rv1Slot)) == 0);
    memcpy(good, file, sizeof(good));
    f = fopen(output, "wb"); CHECK(f != NULL);
    CHECK(fwrite(good, 1, sizeof(good), f) == sizeof(good)); CHECK(fclose(f) == 0);
    pass("real_myset_setting1_setting2_roundtrip_16_slots");

    memset(&sentinel, 0xa5, sizeof(sentinel));
    for (i = 0; i < RV1_FILE_BYTES; ++i) {
        memcpy(file, good, sizeof(good)); file[i] ^= 1;
        memcpy(&decoded, &sentinel, sizeof(decoded));
        CHECK(rv1_decode(file, RV1_FILE_BYTES, &decoded, NULL) != RV1_OK);
        CHECK(memcmp(&decoded, &sentinel, sizeof(decoded)) == 0);
    }
    pass("single_bit_corruption_all_1056_file_bytes_no_partial_decode");
    CHECK(rv1_decode(good, 0, &decoded, NULL) == RV1_LENGTH);
    CHECK(rv1_decode(good, 1055, &decoded, NULL) == RV1_LENGTH);
    CHECK(rv1_decode(file, 1057, &decoded, NULL) == RV1_LENGTH);
    pass("truncated_oversized_files");

    for (i = 0; i < 13; ++i) {
        for (j = 0; j < 2; ++j) {
            memcpy(file, good, sizeof(good)); file[32 + 36 + i] = (uint8_t)(j == 0 ? 0 : 10);
            fix_crcs(file); CHECK(rv1_decode(file, RV1_FILE_BYTES, &decoded, NULL) == RV1_RANGE);
        }
    }
    pass("all_13_raw_fields_reject_0_and_10_with_valid_crc");
    for (i = 0; i < 2; ++i) {
        for (j = 0; j < 2; ++j) {
            memcpy(file, good, sizeof(good)); file[32 + 49 + i] = (uint8_t)(j == 0 ? 247 : 9);
            fix_crcs(file); CHECK(rv1_decode(file, RV1_FILE_BYTES, &decoded, NULL) == RV1_RANGE);
        }
    }
    pass("both_wb_axes_reject_minus9_plus9_with_valid_crc");

    memcpy(file, good, sizeof(good)); file[9] = 3; fix_crcs(file);
    CHECK(rv1_decode(file, RV1_FILE_BYTES, NULL, NULL) == RV1_VERSION);
    memcpy(file, good, sizeof(good)); file[32] = 2; fix_crcs(file);
    CHECK(rv1_decode(file, RV1_FILE_BYTES, NULL, NULL) == RV1_CORRUPT);
    memcpy(file, good, sizeof(good)); file[32 + 3] = 1; fix_crcs(file);
    CHECK(rv1_decode(file, RV1_FILE_BYTES, NULL, NULL) == RV1_VERSION);
    memcpy(file, good, sizeof(good)); file[32 + 2] = 33; fix_crcs(file);
    CHECK(rv1_decode(file, RV1_FILE_BYTES, NULL, NULL) == RV1_RANGE);
    memcpy(file, good, sizeof(good)); file[32 + 4 + 3] = 1; fix_crcs(file);
    CHECK(rv1_decode(file, RV1_FILE_BYTES, NULL, NULL) == RV1_CORRUPT);
    pass("version_slot_reserved_name_length_padding");

    rv1_bank_init(&bank);
    CHECK(rv1_encode(&bank, 1, file, sizeof(file)) == RV1_OK);
    CHECK(rv1_decode(file, RV1_FILE_BYTES, &decoded, NULL) == RV1_OK);
    for (i = 0; i < 16; ++i) CHECK(decoded.slots[i].occupied == 0);
    file[32 + 36] = 3; fix_crcs(file);
    CHECK(rv1_decode(file, RV1_FILE_BYTES, NULL, NULL) == RV1_CORRUPT);
    pass("canonical_empty_slot_and_empty_bank");

    fill_bank(&bank);
    bank.slots[15].recipe.name_length = 32;
    memset(bank.slots[15].recipe.name, 'Z', 32);
    bank.slots[15].recipe.wb[0] = -8; bank.slots[15].recipe.wb[1] = 8;
    for (i = 0; i < 13; ++i) bank.slots[15].recipe.raw[i] = (uint8_t)(i % 9u + 1u);
    CHECK(rv1_encode(&bank, 0, file, sizeof(file)) == RV1_OK);
    CHECK(rv1_decode(file, RV1_FILE_BYTES, &decoded, NULL) == RV1_OK);
    CHECK(memcmp(&decoded.slots[15], &bank.slots[15], sizeof(Rv1Slot)) == 0);
    pass("slot16_name32_all_raw_codes_and_wb_endpoints");
    memset(file, 0xa5, sizeof(file)); memcpy(old, file, sizeof(file));
    bank.slots[15].recipe.raw[0] = 10;
    CHECK(rv1_encode(&bank, 1, file, sizeof(file)) == RV1_RANGE);
    CHECK(memcmp(file, old, sizeof(file)) == 0);
    CHECK(rv1_encode(&bank, 1, file, 1055) == RV1_LENGTH);
    CHECK(memcmp(file, old, sizeof(file)) == 0);
    pass("invalid_encode_leaves_output_unchanged");
}

typedef struct {
    uint8_t data[2][RV1_FILE_BYTES + 1];
    size_t length[2];
    int exists[2], no_card, readonly, full, short_write, close_error, corrupt_readback;
    unsigned writes;
} Card;
static unsigned path_index(const char *path)
{
    if (strcmp(path, "/ATA1/DEEPISP0.DAT") == 0) return 0;
    CHECK(strcmp(path, "/ATA1/DEEPISP1.DAT") == 0); return 1;
}
static Rv1Status card_read(void *context, const char *path, uint8_t *bytes, size_t capacity, size_t *actual)
{
    Card *c = context; unsigned i = path_index(path); size_t n;
    if (c->no_card) return RV1_NO_CARD;
    if (!c->exists[i]) return RV1_EMPTY;
    *actual = c->length[i]; n = *actual < capacity ? *actual : capacity;
    memcpy(bytes, c->data[i], n); return RV1_OK;
}
static Rv1Status card_write(void *context, const char *path, const uint8_t *bytes, size_t length, size_t *actual)
{
    Card *c = context; unsigned i = path_index(path); size_t n = length;
    if (c->no_card) return RV1_NO_CARD;
    if (c->readonly) return RV1_READ_ONLY;
    ++c->writes;
    if (c->full) n /= 2;
    if (c->short_write) --n;
    memcpy(c->data[i], bytes, n); c->exists[i] = 1; c->length[i] = n; *actual = n;
    if (c->full) return RV1_FULL;
    if (c->close_error) return RV1_IO;
    if (c->corrupt_readback) c->data[i][32 + 36] ^= 1;
    return RV1_OK;
}
static void storage_tests(void)
{
    Card c;
    Rv1Store store = {&c, card_read, card_write};
    Rv1Bank bank, loaded, sentinel;
    Rv1StoreInfo info;
    uint8_t scratch[RV1_FILE_BYTES], old[RV1_FILE_BYTES];
    memset(&c, 0, sizeof(c)); fill_bank(&bank);
    memset(&sentinel, 0xa5, sizeof(sentinel)); loaded = sentinel;
    CHECK(rv1_store_load(&store, scratch, sizeof(scratch), &loaded, NULL) == RV1_EMPTY);
    CHECK(memcmp(&loaded, &sentinel, sizeof(loaded)) == 0);
    pass("absent_library_does_not_apply_defaults");
    c.no_card = 1;
    CHECK(rv1_store_load(&store, scratch, sizeof(scratch), &loaded, NULL) == RV1_NO_CARD);
    CHECK(rv1_store_save(&store, scratch, sizeof(scratch), &bank, NULL) == RV1_NO_CARD);
    CHECK(c.writes == 0); CHECK(memcmp(&loaded, &sentinel, sizeof(loaded)) == 0);
    pass("missing_card_load_save_no_mutation");
    c.no_card = 0;
    CHECK(rv1_store_save(&store, scratch, sizeof(scratch), &bank, &info) == RV1_OK);
    CHECK(info.bank_index == 0 && info.generation == 1);
    memcpy(old, c.data[0], sizeof(old));
    bank.slots[0].recipe.raw[0] = 9;
    c.readonly = 1;
    CHECK(rv1_store_save(&store, scratch, sizeof(scratch), &bank, NULL) == RV1_READ_ONLY);
    CHECK(memcmp(old, c.data[0], sizeof(old)) == 0);
    pass("write_protected_card_preserves_previous_bank");
    c.readonly = 0; c.full = 1;
    CHECK(rv1_store_save(&store, scratch, sizeof(scratch), &bank, NULL) == RV1_FULL);
    CHECK(memcmp(old, c.data[0], sizeof(old)) == 0);
    c.full = 0;
    CHECK(rv1_store_load(&store, scratch, sizeof(scratch), &loaded, &info) == RV1_OK);
    CHECK(loaded.generation == 1 && loaded.slots[0].recipe.raw[0] == 8);
    CHECK(info.bank_status[1] == RV1_LENGTH);
    pass("full_card_torn_inactive_bank_falls_back");
    c.short_write = 1;
    CHECK(rv1_store_save(&store, scratch, sizeof(scratch), &bank, NULL) == RV1_IO);
    c.short_write = 0;
    CHECK(rv1_store_load(&store, scratch, sizeof(scratch), &loaded, NULL) == RV1_OK);
    CHECK(loaded.generation == 1);
    pass("short_write_rejected_previous_bank_loads");
    c.corrupt_readback = 1;
    CHECK(rv1_store_save(&store, scratch, sizeof(scratch), &bank, NULL) == RV1_CORRUPT);
    c.corrupt_readback = 0;
    CHECK(rv1_store_load(&store, scratch, sizeof(scratch), &loaded, NULL) == RV1_OK);
    CHECK(loaded.generation == 1);
    pass("readback_corruption_rejected_previous_bank_loads");
    c.close_error = 1;
    CHECK(rv1_store_save(&store, scratch, sizeof(scratch), &bank, NULL) == RV1_IO);
    c.close_error = 0;
    CHECK(memcmp(old, c.data[0], sizeof(old)) == 0);
    pass("close_failure_not_reported_as_success");
    CHECK(rv1_store_load(&store, scratch, sizeof(scratch), &loaded, &info) == RV1_OK);
    CHECK(loaded.generation == 2 && info.bank_index == 1);
    CHECK(rv1_store_save(&store, scratch, sizeof(scratch), &bank, &info) == RV1_OK);
    CHECK(info.generation == 3 && info.bank_index == 0);
    pass("alternating_banks_latest_valid_generation");
    c.data[0][800] ^= 1;
    CHECK(rv1_store_load(&store, scratch, sizeof(scratch), &loaded, NULL) == RV1_OK);
    CHECK(loaded.generation == 2);
    c.data[1][800] ^= 1;
    CHECK(rv1_store_load(&store, scratch, sizeof(scratch), &loaded, NULL) == RV1_CORRUPT);
    CHECK(rv1_store_save(&store, scratch, sizeof(scratch), &bank, NULL) == RV1_CORRUPT);
    pass("both_banks_corrupt_are_not_silently_reinitialized");

    memset(&c, 0, sizeof(c));
    CHECK(rv1_encode(&bank, UINT32_MAX, c.data[0], RV1_FILE_BYTES) == RV1_OK);
    c.exists[0] = 1; c.length[0] = RV1_FILE_BYTES;
    CHECK(rv1_store_save(&store, scratch, sizeof(scratch), &bank, NULL) == RV1_OK);
    CHECK(rv1_store_load(&store, scratch, sizeof(scratch), &loaded, &info) == RV1_OK);
    CHECK(info.generation == 0 && info.bank_index == 1);
    pass("generation_wraparound");
    CHECK(rv1_encode(&bank, UINT32_C(0x80000000), c.data[0], RV1_FILE_BYTES) == RV1_OK);
    CHECK(rv1_store_load(&store, scratch, sizeof(scratch), &loaded, NULL) == RV1_CONFLICT);
    CHECK(rv1_encode(&bank, 0, c.data[0], RV1_FILE_BYTES) == RV1_OK);
    bank.slots[0].recipe.raw[0] = 1;
    CHECK(rv1_encode(&bank, 0, c.data[1], RV1_FILE_BYTES) == RV1_OK);
    CHECK(rv1_store_load(&store, scratch, sizeof(scratch), &loaded, NULL) == RV1_CONFLICT);
    pass("ambiguous_generation_and_equal_generation_different_contents");
    c.data[0][9] = 3; fix_crcs(c.data[0]);
    CHECK(rv1_store_save(&store, scratch, sizeof(scratch), &bank, NULL) == RV1_VERSION);
    pass("future_format_is_not_overwritten");
    memset(&c, 0, sizeof(c)); bank.slots[0].recipe.raw[0] = 0;
    CHECK(rv1_store_save(&store, scratch, sizeof(scratch), &bank, NULL) == RV1_RANGE);
    CHECK(c.writes == 0);
    pass("invalid_recipe_causes_no_file_write");
}

typedef struct {
    uint8_t memory[4096], other[4096];
    volatile uint8_t *selected;
    const uint8_t *preview_expected;
    size_t length;
    unsigned acquisitions, releases, changed, preview_requests;
    int held, unavailable, preview_error;
} Settings;
static Rv1Status settings_acquire(void *context, volatile uint8_t **memory, size_t *length)
{
    Settings *s = context;
    if (s->unavailable) return RV1_IO;
    CHECK(!s->held); s->held = 1; ++s->acquisitions;
    *memory = s->selected; *length = s->length; return RV1_OK;
}
static Rv1Status settings_request_preview(void *context)
{
    Settings *s = context;
    unsigned i;
    CHECK(s->held && s->preview_expected != NULL);
    for (i = 0; i < 4096; ++i) CHECK(s->selected[i] == s->preview_expected[i]);
    CHECK(s->selected[0x36e] == 0x04);
    ++s->preview_requests;
    return s->preview_error ? RV1_IO : RV1_OK;
}
static void settings_release(void *context, int changed)
{
    Settings *s = context; CHECK(s->held); s->held = 0;
    ++s->releases;
    if (changed) { ++s->changed; CHECK(s->preview_requests == s->changed); }
}
static void expected_apply(uint8_t *memory, const Rv1Recipe *r)
{
    unsigned i;
    for (i = 0; i < 3; ++i) memory[0x36f + i] = r->raw[i];
    for (i = 0; i < 5; ++i) { memory[0x8ac + i] = r->raw[3 + i]; memory[0x8b1 + i] = r->raw[8 + i]; }
    memory[0x6dd] = (uint8_t)((int)r->wb[0] + 9);
    memory[0x6de] = (uint8_t)((int)r->wb[1] + 9);
    memory[0x36e] = 0x04;
}
static void application_tests(const char *applied_output)
{
    Settings s;
    Rv1SettingsPort port = {&s, settings_acquire, settings_request_preview, settings_release};
    Rv1Recipe r1 = recipe(1), r2 = recipe(2);
    uint8_t original[4096], expected[4096], before[4096];
    unsigned i, requests, acquisitions;
    memset(&s, 0, sizeof(s));
    for (i = 0; i < sizeof(s.memory); ++i) s.memory[i] = (uint8_t)(i * 37u + 11u);
    s.selected = s.memory; s.length = sizeof(s.memory); s.preview_expected = expected;
    expected_apply(s.memory, &r1);
    for (i = 0; i < 3; ++i) s.memory[0x372 + i] = r2.raw[i];
    for (i = 0; i < 10; ++i) s.memory[0x8b6 + i] = r2.raw[3 + i];
    s.memory[0x36e] = fixture_image_selector;
    CHECK(fixture_image_selector == 0x03); /* A0 was Black & White. */
    memcpy(original, s.memory, sizeof(original));
    r1.wb[0] = -8; r1.wb[1] = 8;
    memcpy(expected, original, sizeof(expected)); expected_apply(expected, &r1);
    CHECK(rv1_apply(&port, &r1) == RV1_OK);
    CHECK(memcmp(s.memory, expected, sizeof(expected)) == 0);
    CHECK(s.memory[0x6dd] == 1 && s.memory[0x6de] == 17);
    CHECK(s.changed == 1 && s.preview_requests == 1);
    pass("apply_setting1_exact_16_offsets_selector04_wb1_17_then_preview_under_ownership");

    s.memory[0x120] = 99;
    memcpy(expected, s.memory, sizeof(expected)); expected_apply(expected, &r2);
    CHECK(rv1_apply(&port, &r2) == RV1_OK);
    CHECK(memcmp(s.memory, expected, sizeof(expected)) == 0);
    CHECK(s.preview_requests == 2);
    CHECK(memcmp(s.memory + 0x36f, fixture_setting2, 3) == 0);
    CHECK(memcmp(s.memory + 0x8ac, fixture_setting2 + 3, 10) == 0);
    CHECK(memcmp(s.memory + 0x372, fixture_setting2, 3) == 0);
    CHECK(memcmp(s.memory + 0x8b6, fixture_setting2 + 3, 10) == 0);
    {
        FILE *f = fopen(applied_output, "wb"); CHECK(f != NULL);
        CHECK(fwrite(s.memory, 1, sizeof(s.memory), f) == sizeof(s.memory));
        CHECK(fclose(f) == 0);
    }
    pass("second_recipe_overwrites_setting1_no_restore_setting2_and_other_edits_intact");

    memcpy(before, s.memory, sizeof(before));
    requests = s.preview_requests; acquisitions = s.acquisitions;
    r1.raw[0] = 0; CHECK(rv1_apply(&port, &r1) == RV1_RANGE);
    r1 = recipe(1); r1.wb[0] = -9; CHECK(rv1_apply(&port, &r1) == RV1_RANGE);
    CHECK(rv1_apply(&port, NULL) == RV1_ARGUMENT);
    CHECK(rv1_apply(NULL, &r2) == RV1_ARGUMENT);
    {
        Rv1SettingsPort incomplete = port;
        incomplete.request_preview = NULL;
        CHECK(rv1_apply(&incomplete, &r2) == RV1_ARGUMENT);
        incomplete = port; incomplete.acquire = NULL;
        CHECK(rv1_apply(&incomplete, &r2) == RV1_ARGUMENT);
        incomplete = port; incomplete.release = NULL;
        CHECK(rv1_apply(&incomplete, &r2) == RV1_ARGUMENT);
    }
    CHECK(s.acquisitions == acquisitions && s.preview_requests == requests);
    CHECK(memcmp(s.memory, before, sizeof(before)) == 0);
    pass("invalid_recipe_and_missing_port_callbacks_do_not_write_or_request_preview");

    s.length = 0x8b5; CHECK(rv1_apply(&port, &r2) == RV1_LENGTH);
    CHECK(!s.held); s.length = 4096;
    s.selected = NULL; CHECK(rv1_apply(&port, &r2) == RV1_LENGTH);
    CHECK(!s.held); s.selected = s.memory;
    s.unavailable = 1; CHECK(rv1_apply(&port, &r2) == RV1_IO); s.unavailable = 0;
    CHECK(s.preview_requests == requests && s.acquisitions == s.releases);
    CHECK(memcmp(s.memory, before, sizeof(before)) == 0);
    pass("short_null_and_unavailable_S_releases_ownership_without_mutation_or_preview");

    memset(s.other, 0xcc, sizeof(s.other)); memcpy(expected, s.other, sizeof(expected));
    r1 = recipe(1); expected_apply(expected, &r1); s.selected = s.other;
    CHECK(rv1_apply(&port, &r1) == RV1_OK);
    CHECK(memcmp(s.other, expected, sizeof(expected)) == 0);
    CHECK(memcmp(s.memory, before, sizeof(before)) == 0);
    pass("acquire_resolves_current_S_each_time_without_cached_identity");

    s.selected = s.memory;
    memcpy(expected, s.memory, sizeof(expected)); expected_apply(expected, &r1);
    s.preview_error = 1; requests = s.preview_requests;
    CHECK(rv1_apply(&port, &r1) == RV1_IO);
    CHECK(memcmp(s.memory, expected, sizeof(expected)) == 0);
    CHECK(!s.held && s.preview_requests == requests + 1 && s.preview_requests == s.changed);
    s.preview_error = 0;
    pass("preview_queue_error_returns_IO_keeps_complete_recipe_and_releases_ownership");

    {
        const uint8_t modes[] = {0x09,0x01,0x0a,0x03,0x06,0x04,0x05};
        for (i = 0; i < sizeof(modes); ++i) {
            memcpy(s.memory, original, sizeof(original)); s.memory[0x36e] = modes[i];
            memcpy(expected, s.memory, sizeof(expected)); expected_apply(expected, &r2);
            CHECK(rv1_apply(&port, &r2) == RV1_OK);
            CHECK(memcmp(s.memory, expected, sizeof(expected)) == 0);
        }
    }
    CHECK(s.acquisitions == s.releases && !s.held && s.preview_requests == s.changed);
    pass("all_seven_native_modes_including_standard01_bw03_become_setting1_04");
}

typedef struct { const char *directory; } FileStore;
static void host_path(char *out, size_t capacity, FileStore *store, const char *path)
{
    int n = snprintf(out, capacity, "%s/RECIPE2%u.DAT", store->directory, path_index(path));
    CHECK(n > 0 && (size_t)n < capacity);
}
static Rv1Status file_read(void *context, const char *path, uint8_t *bytes, size_t capacity, size_t *actual)
{
    char local[2048]; FILE *f; size_t n; int extra, bad;
    host_path(local, sizeof(local), context, path);
    f = fopen(local, "rb");
    if (f == NULL) return errno == ENOENT ? RV1_EMPTY : RV1_IO;
    n = fread(bytes, 1, capacity, f); extra = fgetc(f); bad = ferror(f);
    *actual = n + (extra != EOF ? 1u : 0u);
    if (fclose(f) != 0) bad = 1;
    return bad ? RV1_IO : RV1_OK;
}
static Rv1Status file_write(void *context, const char *path, const uint8_t *bytes, size_t length, size_t *actual)
{
    char local[2048]; FILE *f; int bad;
    host_path(local, sizeof(local), context, path);
    f = fopen(local, "wb"); if (f == NULL) return RV1_IO;
    *actual = fwrite(bytes, 1, length, f); bad = *actual != length;
    if (fflush(f) != 0) bad = 1;
    if (fclose(f) != 0) bad = 1;
    return bad ? RV1_IO : RV1_OK;
}
static void file_roundtrip(const char *directory)
{
    FileStore files = {directory};
    Rv1Store store = {&files, file_read, file_write};
    Rv1Bank bank, loaded; uint8_t scratch[RV1_FILE_BYTES];
    char local[2048]; unsigned i;
    for (i = 0; i < 2; ++i) { host_path(local, sizeof(local), &files, rv1_bank_paths[i]); if (remove(local) != 0) CHECK(errno == ENOENT); }
    fill_bank(&bank);
    CHECK(rv1_store_save(&store, scratch, sizeof(scratch), &bank, NULL) == RV1_OK);
    bank.slots[15].recipe.wb[0] = -8;
    CHECK(rv1_store_save(&store, scratch, sizeof(scratch), &bank, NULL) == RV1_OK);
    CHECK(rv1_store_load(&store, scratch, sizeof(scratch), &loaded, NULL) == RV1_OK);
    CHECK(loaded.generation == 2);
    for (i = 0; i < 16; ++i) CHECK(memcmp(&loaded.slots[i], &bank.slots[i], sizeof(Rv1Slot)) == 0);
    pass("real_host_files_double_bank_roundtrip");
}
int main(int argc, char **argv)
{
    CHECK(argc == 4);
    format_tests(argv[1]); storage_tests(); application_tests(argv[3]); file_roundtrip(argv[2]);
    printf("PASS total_cases=%u\n", cases);
    printf("sizes recipe=%zu bank=%zu settings_port=%zu file=%d\n", sizeof(Rv1Recipe), sizeof(Rv1Bank), sizeof(Rv1SettingsPort), RV1_FILE_BYTES);
    return 0;
}
