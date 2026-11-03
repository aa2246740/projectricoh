#include "internal.h"

static const uint8_t magic[8] = {'G','X','R','R','V','2','0','1'};
#if defined(RFW_DEEP_ENABLED) && !RFW_DEEP_ENABLED
const char rv1_bank_paths[2][19] = {"/ATA1/RECIPE20.DAT", "/ATA1/RECIPE21.DAT"};
#else
const char rv1_bank_paths[2][19] = {"/ATA1/DEEPISP0.DAT", "/ATA1/DEEPISP1.DAT"};
#endif

static Rv1Status validate_parameters(uint8_t mode, const uint8_t *raw)
{
    size_t i, active;
    if (mode == RV1_BASE_COLOR) active = 13;
    else if (mode == RV1_BASE_BW) active = 2;
    else if (mode == RV1_BASE_BW_TE) active = 3;
    else return RV1_VERSION;
    for (i = 0; i < active; ++i)
        if (raw[i] < 1 || raw[i] > 9) return RV1_RANGE;
    if (mode == RV1_BASE_BW_TE) {
        if (raw[3] != 1 && raw[3] != 2 && raw[3] != 3 && raw[3] != 4 && raw[3] != 6)
            return RV1_RANGE;
        active = 4;
    }
    return rv1_zero(raw + active, RV1_COLOR_BYTES - active) ? RV1_OK : RV1_CORRUPT;
}

uint32_t rv1_crc32(const uint8_t *bytes, size_t length)
{
    uint32_t crc = UINT32_C(0xffffffff);
    size_t i;
    unsigned bit;
    for (i = 0; i < length; ++i) {
        crc ^= bytes[i];
        for (bit = 0; bit < 8; ++bit) {
            crc = (crc >> 1) ^ ((crc & 1u) ? UINT32_C(0xedb88320) : 0u);
        }
    }
    return crc ^ UINT32_C(0xffffffff);
}

Rv1Status rv1_validate_recipe(const Rv1Recipe *recipe)
{
    size_t i;
    Rv1Status status;
    if (recipe == NULL) return RV1_ARGUMENT;
    if (recipe->name_length == 0 || recipe->name_length > RV1_NAME_BYTES)
        return RV1_RANGE;
    for (i = 0; i < recipe->name_length; ++i)
        if (recipe->name[i] < 32 || recipe->name[i] > 126) return RV1_RANGE;
    status = validate_parameters(recipe->base_mode, recipe->raw);
    if (status != RV1_OK) return status;
    for (i = 0; i < 2; ++i) {
        if (recipe->wb[i] < -8 || recipe->wb[i] > 8) return RV1_RANGE;
    }
    return RV1_OK;
}

void rv1_bank_init(Rv1Bank *bank)
{
    if (bank != NULL) rv1_clear((uint8_t *)bank, sizeof(*bank));
}

static Rv1Status validate_record(const uint8_t *p, unsigned slot, int legacy)
{
#ifdef RFW_READ_ONLY_BUILD
    legacy = 0;
#endif
    size_t i;
    int wb;
    if (rv1_be32(p + 60) != rv1_crc32(p, 60)) return RV1_CORRUPT;
    Rv1Status status;
    if (p[0] != slot || p[1] > 1 || (legacy && p[3] != 0)) return RV1_CORRUPT;
    if (p[1] == 0) return rv1_zero(p + 2, 58) ? RV1_OK : RV1_CORRUPT;
    if (p[2] < 1 || p[2] > RV1_NAME_BYTES) return RV1_RANGE;
    if (!rv1_zero(p + 4 + p[2], RV1_NAME_BYTES - p[2]) ||
        !rv1_zero(p + 51, 9)) return RV1_CORRUPT;
    if (!legacy)
        for (i = 4; i < 4u + p[2]; ++i)
            if (p[i] < 32 || p[i] > 126) return RV1_RANGE;
    status = validate_parameters(legacy ? RV1_BASE_COLOR : p[3], p + 36);
    if (status != RV1_OK) return status;
    for (i = 49; i < 51; ++i) {
        wb = p[i] <= 127 ? (int)p[i] : (int)p[i] - 256;
        if (wb < -8 || wb > 8) return RV1_RANGE;
    }
    return RV1_OK;
}

#ifndef RFW_READ_ONLY_BUILD
Rv1Status rv1_encode(const Rv1Bank *bank, uint32_t generation,
                     uint8_t *file, size_t capacity)
{
    unsigned slot;
    size_t i;
    uint8_t *p;
    const Rv1Recipe *r;
    Rv1Status status;
    if (bank == NULL || file == NULL) return RV1_ARGUMENT;
    if (capacity < RV1_FILE_BYTES) return RV1_LENGTH;
    for (slot = 0; slot < RV1_SLOT_COUNT; ++slot) {
        if (bank->slots[slot].occupied > 1) return RV1_RANGE;
        if (bank->slots[slot].occupied) {
            status = rv1_validate_recipe(&bank->slots[slot].recipe);
            if (status != RV1_OK) return status;
        }
    }
    rv1_clear(file, RV1_FILE_BYTES);
    for (i = 0; i < sizeof(magic); ++i) file[i] = magic[i];
    file[9] = 2;
    file[11] = RV1_HEADER_BYTES;
    file[13] = RV1_RECORD_BYTES;
    file[15] = RV1_SLOT_COUNT;
    rv1_put32(file + 16, generation);
    rv1_put32(file + 20, RV1_SLOT_COUNT * RV1_RECORD_BYTES);
    for (slot = 0; slot < RV1_SLOT_COUNT; ++slot) {
        p = file + RV1_HEADER_BYTES + slot * RV1_RECORD_BYTES;
        p[0] = (uint8_t)(slot + 1);
        p[1] = bank->slots[slot].occupied;
        if (p[1]) {
            r = &bank->slots[slot].recipe;
            p[2] = r->name_length;
            p[3] = r->base_mode;
            for (i = 0; i < r->name_length; ++i) p[4 + i] = r->name[i];
            for (i = 0; i < RV1_COLOR_BYTES; ++i) p[36 + i] = r->raw[i];
            for (i = 0; i < 2; ++i) p[49 + i] = (uint8_t)r->wb[i];
        }
        rv1_put32(p + 60, rv1_crc32(p, 60));
    }
    rv1_put32(file + 24, rv1_crc32(file + 32, 1024));
    rv1_put32(file + 28, rv1_crc32(file, 28));
    return RV1_OK;
}
#endif

static Rv1Status decode(const uint8_t *file, size_t length,
                       Rv1Bank *out, uint32_t *generation, int legacy)
{
#ifdef RFW_READ_ONLY_BUILD
    legacy = 0;
#endif
    unsigned slot;
    size_t i;
    const uint8_t *p;
    Rv1Recipe *r;
    Rv1Status status;
    int wb;
    if (file == NULL) return RV1_ARGUMENT;
    if (length != RV1_FILE_BYTES) return RV1_LENGTH;
    if (rv1_be32(file + 28) != rv1_crc32(file, 28)) return RV1_CORRUPT;
    /* Recognizable future/foreign formats must not authorize an overwrite. */
    if (!rv1_equal(file, magic, 5) || file[5] != (legacy ? '1' : '2') ||
        file[6] != '0' || file[7] != '1' || file[8] != 0 ||
        file[9] != (legacy ? 1 : 2)) return RV1_VERSION;
    if (file[10] != 0 || file[11] != 32 || file[12] != 0 || file[13] != 64 ||
        file[14] != 0 || file[15] != 16 || rv1_be32(file + 20) != 1024 ||
        rv1_be32(file + 24) != rv1_crc32(file + 32, 1024)) return RV1_CORRUPT;
    for (slot = 0; slot < RV1_SLOT_COUNT; ++slot) {
        status = validate_record(file + 32 + slot * 64, slot + 1, legacy);
        if (status != RV1_OK) return status;
    }
    /* Validate all slots before exposing any decoded recipe. */
    if (out != NULL) {
        rv1_bank_init(out);
        out->generation = rv1_be32(file + 16);
        for (slot = 0; slot < RV1_SLOT_COUNT; ++slot) {
            p = file + 32 + slot * 64;
            out->slots[slot].occupied = p[1];
            if (!p[1]) continue;
            r = &out->slots[slot].recipe;
            r->name_length = p[2];
            r->base_mode = legacy ? RV1_BASE_COLOR : p[3];
            for (i = 0; i < RV1_NAME_BYTES; ++i) r->name[i] = p[4 + i];
            for (i = 0; i < RV1_COLOR_BYTES; ++i) r->raw[i] = p[36 + i];
            for (i = 0; i < 2; ++i) {
                wb = p[49 + i] <= 127 ? (int)p[49 + i] : (int)p[49 + i] - 256;
                r->wb[i] = (int8_t)wb;
            }
        }
    }
    if (generation != NULL) *generation = rv1_be32(file + 16);
    return RV1_OK;
}

Rv1Status rv1_decode(const uint8_t *file, size_t length,
                    Rv1Bank *out, uint32_t *generation)
{
    return decode(file, length, out, generation, 0);
}

#ifndef RFW_READ_ONLY_BUILD
Rv1Status rv1_import_v1(const uint8_t *file, size_t length, Rv1Bank *out)
{
    return decode(file, length, out, NULL, 1);
}
#endif
