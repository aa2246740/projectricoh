#include "recipe_storage.h"

enum {
    RECORD_MAGIC_OFFSET = 0,
    RECORD_MAGIC_LENGTH = 8,
    RECORD_VERSION_OFFSET = 8,
    RECORD_SLOT_OFFSET = 9,
    RECORD_FLAGS_OFFSET = 10,
    RECORD_NAME_LENGTH_OFFSET = 11,
    RECORD_NAME_OFFSET = 12,
    RECORD_COLORS_OFFSET = 44,
    RECORD_RESERVED_OFFSET = 57,
    RECORD_RESERVED_LENGTH = 3,
    RECORD_CRC_OFFSET = 60,
    RECORD_CRC_INPUT_LENGTH = 60,
    RECORD_VERSION = 1
};

static const uint8_t record_magic[RECORD_MAGIC_LENGTH] = {
    'G', 'X', 'R', 'R', 'C', 'P', '0', '1'
};

static int slot_is_valid(RecipeSlot slot)
{
    return slot.one_based >= RECIPE_SLOT_FIRST &&
           slot.one_based <= RECIPE_SLOT_LAST;
}

static void bytes_zero(uint8_t *bytes, size_t length)
{
    size_t index;

    for (index = 0; index < length; ++index) {
        bytes[index] = 0;
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

static uint32_t crc32_iso_hdlc(const uint8_t *bytes, size_t length)
{
    uint32_t crc = UINT32_C(0xffffffff);
    size_t index;
    unsigned bit;

    for (index = 0; index < length; ++index) {
        crc ^= bytes[index];
        for (bit = 0; bit < 8; ++bit) {
            uint32_t mask = UINT32_C(0) - (crc & UINT32_C(1));
            crc = (crc >> 1) ^ (UINT32_C(0xedb88320) & mask);
        }
    }
    return crc ^ UINT32_C(0xffffffff);
}

static void store_u32_be(uint8_t *output, uint32_t value)
{
    output[0] = (uint8_t)(value >> 24);
    output[1] = (uint8_t)(value >> 16);
    output[2] = (uint8_t)(value >> 8);
    output[3] = (uint8_t)value;
}

static uint32_t load_u32_be(const uint8_t *input)
{
    return ((uint32_t)input[0] << 24) |
           ((uint32_t)input[1] << 16) |
           ((uint32_t)input[2] << 8) |
           (uint32_t)input[3];
}

static RecipeStatus validate_name(const RecipeName *name)
{
    if (name->length == 0 || name->length > RECIPE_NAME_CAPACITY) {
        return RECIPE_BAD_NAME;
    }
    return RECIPE_OK;
}

static void copy_recipe(Recipe *output, const Recipe *input)
{
    size_t index;

    output->name.length = input->name.length;
    for (index = 0; index < RECIPE_NAME_CAPACITY; ++index) {
        output->name.bytes[index] = input->name.bytes[index];
    }
    for (index = 0; index < RECIPE_COLOR_VALUE_COUNT; ++index) {
        output->colors.bytes[index] = input->colors.bytes[index];
    }
}

static RecipeStatus encode_record(
    RecipeSlot slot,
    const Recipe *recipe,
    uint8_t *record)
{
    size_t index;
    uint32_t crc;

    if (validate_name(&recipe->name) != RECIPE_OK) {
        return RECIPE_BAD_NAME;
    }

    bytes_zero(record, RECIPE_RECORD_SIZE);
    for (index = 0; index < RECORD_MAGIC_LENGTH; ++index) {
        record[RECORD_MAGIC_OFFSET + index] = record_magic[index];
    }
    record[RECORD_VERSION_OFFSET] = RECORD_VERSION;
    record[RECORD_SLOT_OFFSET] = slot.one_based;
    record[RECORD_NAME_LENGTH_OFFSET] = recipe->name.length;
    for (index = 0; index < recipe->name.length; ++index) {
        record[RECORD_NAME_OFFSET + index] = recipe->name.bytes[index];
    }
    for (index = 0; index < RECIPE_COLOR_VALUE_COUNT; ++index) {
        record[RECORD_COLORS_OFFSET + index] = recipe->colors.bytes[index];
    }
    crc = crc32_iso_hdlc(record, RECORD_CRC_INPUT_LENGTH);
    store_u32_be(&record[RECORD_CRC_OFFSET], crc);
    return RECIPE_OK;
}

static RecipeStatus decode_record(
    const uint8_t *record,
    RecipeSlot expected_slot,
    Recipe *recipe)
{
    Recipe decoded;
    uint8_t name_length;
    uint32_t expected_crc;
    uint32_t actual_crc;
    size_t index;

    if (!bytes_equal(record, record_magic, RECORD_MAGIC_LENGTH) ||
        record[RECORD_VERSION_OFFSET] != RECORD_VERSION ||
        record[RECORD_SLOT_OFFSET] != expected_slot.one_based ||
        record[RECORD_FLAGS_OFFSET] != 0) {
        return RECIPE_CORRUPT;
    }

    name_length = record[RECORD_NAME_LENGTH_OFFSET];
    if (name_length == 0 || name_length > RECIPE_NAME_CAPACITY) {
        return RECIPE_CORRUPT;
    }
    for (index = name_length; index < RECIPE_NAME_CAPACITY; ++index) {
        if (record[RECORD_NAME_OFFSET + index] != 0) {
            return RECIPE_CORRUPT;
        }
    }
    for (index = 0; index < RECORD_RESERVED_LENGTH; ++index) {
        if (record[RECORD_RESERVED_OFFSET + index] != 0) {
            return RECIPE_CORRUPT;
        }
    }

    expected_crc = crc32_iso_hdlc(record, RECORD_CRC_INPUT_LENGTH);
    actual_crc = load_u32_be(&record[RECORD_CRC_OFFSET]);
    if (actual_crc != expected_crc) {
        return RECIPE_CORRUPT;
    }

    decoded.name.length = name_length;
    for (index = 0; index < RECIPE_NAME_CAPACITY; ++index) {
        decoded.name.bytes[index] = record[RECORD_NAME_OFFSET + index];
    }
    for (index = 0; index < RECIPE_COLOR_VALUE_COUNT; ++index) {
        decoded.colors.bytes[index] = record[RECORD_COLORS_OFFSET + index];
    }
    copy_recipe(recipe, &decoded);
    return RECIPE_OK;
}

static int recipe_matches(const Recipe *left, const Recipe *right)
{
    if (left->name.length != right->name.length) {
        return 0;
    }
    if (!bytes_equal(left->name.bytes, right->name.bytes, left->name.length)) {
        return 0;
    }
    return bytes_equal(
        left->colors.bytes,
        right->colors.bytes,
        RECIPE_COLOR_VALUE_COUNT);
}

RecipeStatus recipe_read(RecipeCore *core, RecipeSlot slot, Recipe *out_recipe)
{
    uint8_t record[RECIPE_RECORD_SIZE];
    Recipe decoded;
    RecipeStoreStatus store_status;
    RecipeStatus decode_status;
    size_t actual_length = 0;

    if (core == NULL || out_recipe == NULL || core->storage.read == NULL) {
        return RECIPE_BAD_ARGUMENT;
    }
    if (!slot_is_valid(slot)) {
        return RECIPE_BAD_SLOT;
    }

    bytes_zero(record, RECIPE_RECORD_SIZE);
    store_status = core->storage.read(
        core->storage.context,
        slot,
        record,
        RECIPE_RECORD_SIZE,
        &actual_length);
    if (store_status == RECIPE_STORE_MISSING) {
        return RECIPE_EMPTY;
    }
    if (store_status != RECIPE_STORE_OK) {
        return RECIPE_IO_ERROR;
    }
    if (actual_length != RECIPE_RECORD_SIZE) {
        return RECIPE_CORRUPT;
    }

    decode_status = decode_record(record, slot, &decoded);
    if (decode_status != RECIPE_OK) {
        return decode_status;
    }
    copy_recipe(out_recipe, &decoded);
    return RECIPE_OK;
}

RecipeStatus recipe_save(RecipeCore *core, RecipeSlot slot, const Recipe *recipe)
{
    uint8_t record[RECIPE_RECORD_SIZE];
    Recipe stored_recipe;
    RecipeStoreStatus store_status;
    RecipeStatus status;
    size_t written_length = 0;
    size_t actual_length = 0;

    if (core == NULL || recipe == NULL || core->storage.write == NULL ||
        core->storage.read == NULL) {
        return RECIPE_BAD_ARGUMENT;
    }
    if (!slot_is_valid(slot)) {
        return RECIPE_BAD_SLOT;
    }

    status = encode_record(slot, recipe, record);
    if (status != RECIPE_OK) {
        return status;
    }
    store_status = core->storage.write(
        core->storage.context,
        slot,
        record,
        RECIPE_RECORD_SIZE,
        &written_length);
    if (store_status != RECIPE_STORE_OK || written_length != RECIPE_RECORD_SIZE) {
        return RECIPE_IO_ERROR;
    }

    bytes_zero(record, RECIPE_RECORD_SIZE);
    store_status = core->storage.read(
        core->storage.context,
        slot,
        record,
        RECIPE_RECORD_SIZE,
        &actual_length);
    if (store_status != RECIPE_STORE_OK) {
        return RECIPE_IO_ERROR;
    }
    if (actual_length != RECIPE_RECORD_SIZE) {
        return RECIPE_CORRUPT;
    }
    status = decode_record(record, slot, &stored_recipe);
    if (status != RECIPE_OK) {
        return status;
    }
    if (!recipe_matches(&stored_recipe, recipe)) {
        return RECIPE_CORRUPT;
    }
    return RECIPE_OK;
}

RecipeStatus recipe_delete(RecipeCore *core, RecipeSlot slot)
{
    uint8_t record[RECIPE_RECORD_SIZE];
    RecipeStoreStatus store_status;
    size_t actual_length = 0;

    if (core == NULL || core->storage.remove == NULL ||
        core->storage.read == NULL) {
        return RECIPE_BAD_ARGUMENT;
    }
    if (!slot_is_valid(slot)) {
        return RECIPE_BAD_SLOT;
    }

    store_status = core->storage.remove(core->storage.context, slot);
    if (store_status != RECIPE_STORE_OK &&
        store_status != RECIPE_STORE_MISSING) {
        return RECIPE_IO_ERROR;
    }

    store_status = core->storage.read(
        core->storage.context,
        slot,
        record,
        RECIPE_RECORD_SIZE,
        &actual_length);
    if (store_status == RECIPE_STORE_MISSING) {
        return RECIPE_OK;
    }
    return RECIPE_IO_ERROR;
}
