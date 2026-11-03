#include "../recipe_core.h"
#include "../recipe_storage.h"
#include "host_file_store.h"

#include <errno.h>
#include <stdio.h>
#include <sys/stat.h>

typedef struct {
    uint8_t records[RECIPE_SLOT_LAST][RECIPE_RECORD_SIZE];
    size_t lengths[RECIPE_SLOT_LAST];
    uint8_t exists[RECIPE_SLOT_LAST];
    int read_override_enabled;
    RecipeStoreStatus read_override_status;
    uint8_t read_override_record[RECIPE_RECORD_SIZE];
    size_t read_override_length;
    int write_override_enabled;
    RecipeStoreStatus write_override_status;
    size_t write_override_length;
    int remove_override_enabled;
    RecipeStoreStatus remove_override_status;
    int remove_leaves_record;
    unsigned read_calls;
    unsigned write_calls;
    unsigned remove_calls;
} FakeStore;

typedef struct {
    uint32_t picture_quality;
    uint32_t exposure;
    uint32_t focus;
} UnprovidedCameraState;

static unsigned check_count;
static unsigned failure_count;

static const uint8_t golden_record[RECIPE_RECORD_SIZE] = {
    [0] = 'G', [1] = 'X', [2] = 'R', [3] = 'R',
    [4] = 'C', [5] = 'P', [6] = '0', [7] = '1',
    [8] = 1, [9] = 7, [11] = 3,
    [12] = 0x41, [13] = 0x00, [14] = 0xff,
    [44] = 0x00, [45] = 0x11, [46] = 0x22, [47] = 0x33,
    [48] = 0x44, [49] = 0x55, [50] = 0x66, [51] = 0x77,
    [52] = 0x88, [53] = 0x99, [54] = 0xaa, [55] = 0xbb,
    [56] = 0xcc,
    [60] = 0x2f, [61] = 0xf8, [62] = 0x0a, [63] = 0xb5
};

static void check_result(int condition, const char *expression, int line)
{
    ++check_count;
    if (!condition) {
        ++failure_count;
        (void)fprintf(stderr, "FAIL line %d: %s\n", line, expression);
    }
}

#define CHECK(expression) check_result((expression), #expression, __LINE__)

static void bytes_fill(uint8_t *bytes, size_t length, uint8_t value)
{
    size_t index;

    for (index = 0; index < length; ++index) {
        bytes[index] = value;
    }
}

static void bytes_copy(uint8_t *output, const uint8_t *input, size_t length)
{
    size_t index;

    for (index = 0; index < length; ++index) {
        output[index] = input[index];
    }
}

static int bytes_equal(const uint8_t *left, const uint8_t *right, size_t length)
{
    size_t index;

    for (index = 0; index < length; ++index) {
        if (left[index] != right[index]) {
            return 0;
        }
    }
    return 1;
}

static Recipe make_recipe(uint8_t seed, uint8_t name_length)
{
    Recipe recipe;
    size_t index;

    recipe.name.length = name_length;
    bytes_fill(recipe.name.bytes, RECIPE_NAME_CAPACITY, 0);
    for (index = 0; index < name_length && index < RECIPE_NAME_CAPACITY; ++index) {
        recipe.name.bytes[index] = (uint8_t)(seed + (uint8_t)(index * 17U));
    }
    for (index = 0; index < RECIPE_COLOR_VALUE_COUNT; ++index) {
        recipe.colors.bytes[index] = (uint8_t)(seed + (uint8_t)(index * 3U));
    }
    return recipe;
}

static Recipe make_golden_recipe(void)
{
    Recipe recipe = make_recipe(0, 3);
    size_t index;

    recipe.name.bytes[0] = 0x41;
    recipe.name.bytes[1] = 0x00;
    recipe.name.bytes[2] = 0xff;
    for (index = 0; index < RECIPE_COLOR_VALUE_COUNT; ++index) {
        recipe.colors.bytes[index] = (uint8_t)(index * 17U);
    }
    return recipe;
}

static int recipes_equal(const Recipe *left, const Recipe *right)
{
    return left->name.length == right->name.length &&
           bytes_equal(left->name.bytes, right->name.bytes, RECIPE_NAME_CAPACITY) &&
           bytes_equal(
               left->colors.bytes,
               right->colors.bytes,
               RECIPE_COLOR_VALUE_COUNT);
}

static RecipeStoreStatus fake_read(
    void *context,
    RecipeSlot slot,
    uint8_t *record,
    size_t capacity,
    size_t *actual_length)
{
    FakeStore *store = context;
    size_t slot_index = (size_t)slot.one_based - 1U;
    const uint8_t *source;
    size_t length;
    size_t copy_length;

    ++store->read_calls;
    if (store->read_override_enabled != 0) {
        if (store->read_override_status != RECIPE_STORE_OK) {
            return store->read_override_status;
        }
        source = store->read_override_record;
        length = store->read_override_length;
    } else {
        if (store->exists[slot_index] == 0) {
            return RECIPE_STORE_MISSING;
        }
        source = store->records[slot_index];
        length = store->lengths[slot_index];
    }

    *actual_length = length;
    copy_length = length < capacity ? length : capacity;
    bytes_copy(record, source, copy_length);
    return RECIPE_STORE_OK;
}

static RecipeStoreStatus fake_write(
    void *context,
    RecipeSlot slot,
    const uint8_t *record,
    size_t length,
    size_t *written_length)
{
    FakeStore *store = context;
    size_t slot_index = (size_t)slot.one_based - 1U;
    size_t copy_length = length < RECIPE_RECORD_SIZE ? length : RECIPE_RECORD_SIZE;

    ++store->write_calls;
    if (store->write_override_enabled != 0 &&
        store->write_override_status != RECIPE_STORE_OK) {
        return store->write_override_status;
    }
    bytes_copy(store->records[slot_index], record, copy_length);
    store->lengths[slot_index] = length;
    store->exists[slot_index] = 1;
    *written_length = store->write_override_enabled != 0
        ? store->write_override_length
        : length;
    return RECIPE_STORE_OK;
}

static RecipeStoreStatus fake_remove(void *context, RecipeSlot slot)
{
    FakeStore *store = context;
    size_t slot_index = (size_t)slot.one_based - 1U;

    ++store->remove_calls;
    if (store->remove_override_enabled != 0) {
        if (store->remove_override_status != RECIPE_STORE_OK) {
            return store->remove_override_status;
        }
        if (store->remove_leaves_record != 0) {
            return RECIPE_STORE_OK;
        }
    }
    if (store->exists[slot_index] == 0) {
        return RECIPE_STORE_MISSING;
    }
    store->exists[slot_index] = 0;
    store->lengths[slot_index] = 0;
    return RECIPE_STORE_OK;
}

static RecipeCore fake_core(FakeStore *store)
{
    RecipeCore core;

    core.storage.context = store;
    core.storage.read = fake_read;
    core.storage.write = fake_write;
    core.storage.remove = fake_remove;
    return core;
}

static void fill_output_sentinel(Recipe *recipe)
{
    recipe->name.length = 0xa5;
    bytes_fill(recipe->name.bytes, RECIPE_NAME_CAPACITY, 0xa5);
    bytes_fill(recipe->colors.bytes, RECIPE_COLOR_VALUE_COUNT, 0xa5);
}

static int output_is_sentinel(const Recipe *recipe)
{
    size_t index;

    if (recipe->name.length != 0xa5) {
        return 0;
    }
    for (index = 0; index < RECIPE_NAME_CAPACITY; ++index) {
        if (recipe->name.bytes[index] != 0xa5) {
            return 0;
        }
    }
    for (index = 0; index < RECIPE_COLOR_VALUE_COUNT; ++index) {
        if (recipe->colors.bytes[index] != 0xa5) {
            return 0;
        }
    }
    return 1;
}

static void test_all_slots_and_isolation(void)
{
    FakeStore store = {0};
    RecipeCore core = fake_core(&store);
    uint8_t snapshot[RECIPE_SLOT_LAST][RECIPE_RECORD_SIZE];
    unsigned slot_number;
    unsigned other_slot;

    for (slot_number = RECIPE_SLOT_FIRST; slot_number <= RECIPE_SLOT_LAST;
         ++slot_number) {
        Recipe recipe = make_recipe(
            (uint8_t)(slot_number * 7U),
            (uint8_t)slot_number);
        RecipeSlot slot = {(uint8_t)slot_number};

        CHECK(recipe_save(&core, slot, &recipe) == RECIPE_OK);
        bytes_copy(
            snapshot[slot_number - 1U],
            store.records[slot_number - 1U],
            RECIPE_RECORD_SIZE);
    }

    for (slot_number = RECIPE_SLOT_FIRST; slot_number <= RECIPE_SLOT_LAST;
         ++slot_number) {
        Recipe expected = make_recipe(
            (uint8_t)(slot_number * 7U),
            (uint8_t)slot_number);
        Recipe actual;
        RecipeSlot slot = {(uint8_t)slot_number};

        fill_output_sentinel(&actual);
        CHECK(recipe_read(&core, slot, &actual) == RECIPE_OK);
        CHECK(recipes_equal(&actual, &expected));
        for (other_slot = slot_number + 1U;
             other_slot <= RECIPE_SLOT_LAST;
             ++other_slot) {
            CHECK(!bytes_equal(
                store.records[slot_number - 1U],
                store.records[other_slot - 1U],
                RECIPE_RECORD_SIZE));
        }
    }

    {
        Recipe replacement = make_recipe(0xe0, 8);
        RecipeSlot slot = {8};

        CHECK(recipe_save(&core, slot, &replacement) == RECIPE_OK);
        for (slot_number = RECIPE_SLOT_FIRST; slot_number <= RECIPE_SLOT_LAST;
             ++slot_number) {
            if (slot_number == 8U) {
                CHECK(!bytes_equal(
                    store.records[slot_number - 1U],
                    snapshot[slot_number - 1U],
                    RECIPE_RECORD_SIZE));
            } else {
                CHECK(bytes_equal(
                    store.records[slot_number - 1U],
                    snapshot[slot_number - 1U],
                    RECIPE_RECORD_SIZE));
            }
        }
    }
}

static void test_arguments_names_and_null_save(void)
{
    FakeStore store = {0};
    RecipeCore core = fake_core(&store);
    Recipe recipe = make_recipe(1, 4);
    Recipe output;
    RecipeSlot zero = {0};
    RecipeSlot seventeen = {17};
    RecipeSlot one = {1};
    unsigned remove_calls;
    unsigned write_calls;

    fill_output_sentinel(&output);
    CHECK(recipe_read(&core, zero, &output) == RECIPE_BAD_SLOT);
    CHECK(output_is_sentinel(&output));
    CHECK(recipe_read(&core, seventeen, &output) == RECIPE_BAD_SLOT);
    CHECK(output_is_sentinel(&output));
    CHECK(recipe_save(&core, zero, &recipe) == RECIPE_BAD_SLOT);
    CHECK(recipe_save(&core, seventeen, &recipe) == RECIPE_BAD_SLOT);
    CHECK(recipe_delete(&core, zero) == RECIPE_BAD_SLOT);
    CHECK(recipe_delete(&core, seventeen) == RECIPE_BAD_SLOT);

    recipe.name.length = 0;
    CHECK(recipe_save(&core, one, &recipe) == RECIPE_BAD_NAME);
    recipe.name.length = 33;
    CHECK(recipe_save(&core, one, &recipe) == RECIPE_BAD_NAME);
    recipe = make_recipe(2, 1);
    CHECK(recipe_save(&core, one, &recipe) == RECIPE_OK);
    recipe = make_recipe(3, 32);
    CHECK(recipe_save(&core, one, &recipe) == RECIPE_OK);

    remove_calls = store.remove_calls;
    write_calls = store.write_calls;
    CHECK(recipe_save(&core, one, NULL) == RECIPE_BAD_ARGUMENT);
    CHECK(store.remove_calls == remove_calls);
    CHECK(store.write_calls == write_calls);
    CHECK(recipe_read(&core, one, &output) == RECIPE_OK);
    CHECK(recipes_equal(&output, &recipe));
}

static void test_delete_and_store_errors(void)
{
    FakeStore store = {0};
    RecipeCore core = fake_core(&store);
    Recipe recipe = make_recipe(8, 8);
    Recipe output;
    RecipeSlot slot = {2};

    CHECK(recipe_save(&core, slot, &recipe) == RECIPE_OK);
    CHECK(recipe_delete(&core, slot) == RECIPE_OK);
    fill_output_sentinel(&output);
    CHECK(recipe_read(&core, slot, &output) == RECIPE_EMPTY);
    CHECK(output_is_sentinel(&output));
    CHECK(recipe_delete(&core, slot) == RECIPE_OK);

    CHECK(recipe_save(&core, slot, &recipe) == RECIPE_OK);
    store.remove_override_enabled = 1;
    store.remove_override_status = RECIPE_STORE_IO;
    CHECK(recipe_delete(&core, slot) == RECIPE_IO_ERROR);
    store.remove_override_status = RECIPE_STORE_OK;
    store.remove_leaves_record = 1;
    CHECK(recipe_delete(&core, slot) == RECIPE_IO_ERROR);
}

static int write_binary(const char *path, const uint8_t *bytes, size_t length)
{
    FILE *file = fopen(path, "wb");
    size_t written;
    int failed;
    int close_result;

    if (file == NULL) {
        return 0;
    }
    written = fwrite(bytes, 1, length, file);
    failed = ferror(file);
    close_result = fclose(file);
    return written == length && failed == 0 && close_result == 0;
}

static void set_crc(uint8_t *record, uint8_t a, uint8_t b, uint8_t c, uint8_t d)
{
    record[60] = a;
    record[61] = b;
    record[62] = c;
    record[63] = d;
}

static void expect_corrupt_unchanged(
    RecipeCore *core,
    RecipeSlot slot,
    Recipe *output)
{
    fill_output_sentinel(output);
    CHECK(recipe_read(core, slot, output) == RECIPE_CORRUPT);
    CHECK(output_is_sentinel(output));
}

static void test_corrupt_records_and_golden(const char *artifact_directory)
{
    FakeStore store = {0};
    RecipeCore core = fake_core(&store);
    Recipe recipe = make_golden_recipe();
    Recipe output;
    RecipeSlot seven = {7};
    RecipeSlot eight = {8};
    char path[1024];
    int path_length;

    CHECK(recipe_save(&core, seven, &recipe) == RECIPE_OK);
    CHECK(bytes_equal(store.records[6], golden_record, RECIPE_RECORD_SIZE));
    path_length = snprintf(path, sizeof(path), "%s/golden.bin", artifact_directory);
    CHECK(path_length > 0 && (size_t)path_length < sizeof(path));
    CHECK(write_binary(path, store.records[6], RECIPE_RECORD_SIZE));

    store.lengths[6] = 63;
    expect_corrupt_unchanged(&core, seven, &output);
    store.lengths[6] = 65;
    expect_corrupt_unchanged(&core, seven, &output);
    store.lengths[6] = RECIPE_RECORD_SIZE;

    bytes_copy(store.records[6], golden_record, RECIPE_RECORD_SIZE);
    store.records[6][60] ^= 1U;
    expect_corrupt_unchanged(&core, seven, &output);

    bytes_copy(store.records[7], golden_record, RECIPE_RECORD_SIZE);
    store.exists[7] = 1;
    store.lengths[7] = RECIPE_RECORD_SIZE;
    expect_corrupt_unchanged(&core, eight, &output);

    bytes_copy(store.records[6], golden_record, RECIPE_RECORD_SIZE);
    store.records[6][10] = 1;
    set_crc(store.records[6], 0xab, 0xc9, 0x13, 0x44);
    expect_corrupt_unchanged(&core, seven, &output);

    bytes_copy(store.records[6], golden_record, RECIPE_RECORD_SIZE);
    store.records[6][15] = 1;
    set_crc(store.records[6], 0x8c, 0x6e, 0x22, 0xf9);
    expect_corrupt_unchanged(&core, seven, &output);

    bytes_copy(store.records[6], golden_record, RECIPE_RECORD_SIZE);
    store.records[6][57] = 1;
    set_crc(store.records[6], 0x2e, 0x3a, 0x60, 0x82);
    expect_corrupt_unchanged(&core, seven, &output);

    store.read_override_enabled = 1;
    store.read_override_status = RECIPE_STORE_IO;
    fill_output_sentinel(&output);
    CHECK(recipe_read(&core, seven, &output) == RECIPE_IO_ERROR);
    CHECK(output_is_sentinel(&output));
}

static void test_save_failures_and_readback_mismatch(void)
{
    FakeStore store = {0};
    RecipeCore core = fake_core(&store);
    Recipe first = make_recipe(0x21, 5);
    Recipe second = make_recipe(0x42, 5);
    RecipeSlot slot = {5};

    store.write_override_enabled = 1;
    store.write_override_status = RECIPE_STORE_IO;
    CHECK(recipe_save(&core, slot, &first) == RECIPE_IO_ERROR);

    store.write_override_status = RECIPE_STORE_OK;
    store.write_override_length = 63;
    CHECK(recipe_save(&core, slot, &first) == RECIPE_IO_ERROR);

    store.write_override_enabled = 0;
    CHECK(recipe_save(&core, slot, &first) == RECIPE_OK);
    bytes_copy(
        store.read_override_record,
        store.records[4],
        RECIPE_RECORD_SIZE);
    store.read_override_length = RECIPE_RECORD_SIZE;
    store.read_override_status = RECIPE_STORE_OK;
    store.read_override_enabled = 1;
    CHECK(recipe_save(&core, slot, &second) == RECIPE_CORRUPT);

    store.read_override_status = RECIPE_STORE_MISSING;
    CHECK(recipe_save(&core, slot, &second) == RECIPE_IO_ERROR);
    store.read_override_status = RECIPE_STORE_IO;
    CHECK(recipe_save(&core, slot, &second) == RECIPE_IO_ERROR);
    store.read_override_status = RECIPE_STORE_OK;
    store.read_override_length = 63;
    CHECK(recipe_save(&core, slot, &second) == RECIPE_CORRUPT);
}

static void test_unprovided_camera_state(void)
{
    FakeStore store = {0};
    RecipeCore core = fake_core(&store);
    Recipe recipe = make_recipe(9, 9);
    Recipe output;
    RecipeSlot slot = {9};
    UnprovidedCameraState state = {
        UINT32_C(0x11223344),
        UINT32_C(0x55667788),
        UINT32_C(0x99aabbcc)
    };

    CHECK(recipe_save(&core, slot, &recipe) == RECIPE_OK);
    CHECK(recipe_read(&core, slot, &output) == RECIPE_OK);
    CHECK(recipe_delete(&core, slot) == RECIPE_OK);
    CHECK(state.picture_quality == UINT32_C(0x11223344));
    CHECK(state.exposure == UINT32_C(0x55667788));
    CHECK(state.focus == UINT32_C(0x99aabbcc));
}

static void test_host_file_round_trip(const char *artifact_directory)
{
    char directory[1024];
    int path_length = snprintf(
        directory,
        sizeof(directory),
        "%s/host-files",
        artifact_directory);
    HostFileStore store;
    RecipeCore writer;
    RecipeCore reader;
    Recipe expected = make_recipe(0x61, 16);
    Recipe actual;
    RecipeSlot slot = {16};

    CHECK(path_length > 0 && (size_t)path_length < sizeof(directory));
    CHECK(mkdir(directory, 0777) == 0 || errno == EEXIST);
    store.directory = directory;
    writer.storage = host_file_storage(&store);
    CHECK(recipe_delete(&writer, slot) == RECIPE_OK);
    CHECK(recipe_save(&writer, slot, &expected) == RECIPE_OK);

    reader.storage = host_file_storage(&store);
    fill_output_sentinel(&actual);
    CHECK(recipe_read(&reader, slot, &actual) == RECIPE_OK);
    CHECK(recipes_equal(&actual, &expected));
}

int main(int argc, char **argv)
{
    if (argc != 2) {
        (void)fprintf(stderr, "usage: %s ARTIFACT_DIRECTORY\n", argv[0]);
        return 2;
    }

    test_all_slots_and_isolation();
    test_arguments_names_and_null_save();
    test_delete_and_store_errors();
    test_corrupt_records_and_golden(argv[1]);
    test_save_failures_and_readback_mismatch();
    test_unprovided_camera_state();
    test_host_file_round_trip(argv[1]);

    if (failure_count != 0) {
        (void)fprintf(
            stderr,
            "FAIL recipe_core checks=%u failures=%u\n",
            check_count,
            failure_count);
        return 1;
    }
    (void)printf("PASS recipe_core checks=%u\n", check_count);
    return 0;
}
