#include "internal.h"

static void copy_info(Rv1StoreInfo *out, const Rv1StoreInfo *in)
{
    out->generation = in->generation;
    out->bank_index = in->bank_index;
    out->bank_status[0] = in->bank_status[0];
    out->bank_status[1] = in->bank_status[1];
}

static void init_info(Rv1StoreInfo *info)
{
    info->generation = 0;
    info->bank_index = 0;
    info->bank_status[0] = RV1_EMPTY;
    info->bank_status[1] = RV1_EMPTY;
}

static Rv1Status read_bank(const Rv1Store *store, unsigned index,
                           uint8_t *scratch, uint32_t *generation)
{
    size_t actual = 0;
    Rv1Status status = store->read(store->context, rv1_bank_paths[index],
                                  scratch, RV1_FILE_BYTES, &actual);
    if (status != RV1_OK) return status;
    return rv1_decode(scratch, actual, NULL, generation);
}

static int recoverable(Rv1Status status)
{
    return status == RV1_OK || status == RV1_EMPTY || status == RV1_LENGTH ||
           status == RV1_CORRUPT || status == RV1_RANGE;
}

static Rv1Status scan(const Rv1Store *store, uint8_t *scratch,
                       Rv1StoreInfo *info)
{
    uint32_t gen[2] = {0, 0};
    uint32_t delta;
    unsigned i;
    for (i = 0; i < 2; ++i) {
        info->bank_status[i] = read_bank(store, i, scratch, &gen[i]);
        /* Future formats and media errors cannot authorize overwriting a bank. */
        if (!recoverable(info->bank_status[i])) return info->bank_status[i];
    }
    if (info->bank_status[0] != RV1_OK && info->bank_status[1] != RV1_OK) {
        if (info->bank_status[0] == RV1_EMPTY && info->bank_status[1] == RV1_EMPTY)
            return RV1_EMPTY;
        return RV1_CORRUPT;
    }
    i = info->bank_status[0] == RV1_OK ? 0u : 1u;
    if (info->bank_status[0] == RV1_OK && info->bank_status[1] == RV1_OK) {
        delta = gen[1] - gen[0];
        if (delta == UINT32_C(0x80000000)) return RV1_CONFLICT;
        if (delta != 0 && delta < UINT32_C(0x80000000)) i = 1;
        if (delta == 0) {
            uint32_t first_crc;
            Rv1Status status = read_bank(store, 0, scratch, NULL);
            if (status != RV1_OK) return status;
            first_crc = rv1_crc32(scratch, RV1_FILE_BYTES);
            status = read_bank(store, 1, scratch, NULL);
            if (status != RV1_OK) return status;
            if (first_crc != rv1_crc32(scratch, RV1_FILE_BYTES)) return RV1_CONFLICT;
        }
    }
    info->bank_index = (uint8_t)i;
    info->generation = gen[i];
    return RV1_OK;
}

static int valid_port(const Rv1Store *store, uint8_t *scratch, size_t capacity)
{
    return store != NULL && scratch != NULL && capacity >= RV1_FILE_BYTES &&
           store->read != NULL;
}

Rv1Status rv1_store_load(const Rv1Store *store, uint8_t *scratch,
                         size_t capacity, Rv1Bank *out, Rv1StoreInfo *info)
{
    Rv1StoreInfo selected;
    Rv1Status status;
    uint32_t gen;
    if (!valid_port(store, scratch, capacity) || out == NULL) return RV1_ARGUMENT;
    init_info(&selected);
    status = scan(store, scratch, &selected);
    if (status != RV1_OK) return status;
    status = read_bank(store, selected.bank_index, scratch, &gen);
    if (status != RV1_OK) return status;
    if (gen != selected.generation) return RV1_CONFLICT;
    status = rv1_decode(scratch, RV1_FILE_BYTES, out, NULL);
    if (status == RV1_OK && info != NULL) copy_info(info, &selected);
    return status;
}

Rv1Status rv1_store_save(const Rv1Store *store, uint8_t *scratch,
                         size_t capacity, const Rv1Bank *bank,
                         Rv1StoreInfo *info)
{
    Rv1StoreInfo selected;
    Rv1Status status;
    uint32_t expected_crc;
    uint32_t generation;
    unsigned destination;
    size_t written = 0;
    if (!valid_port(store, scratch, capacity) || bank == NULL || store->write == NULL)
        return RV1_ARGUMENT;
    init_info(&selected);
    /* Invalid recipes never cause a file mutation, even on an empty card. */
    status = rv1_encode(bank, 0, scratch, capacity);
    if (status != RV1_OK) return status;
    status = scan(store, scratch, &selected);
    if (status != RV1_OK && status != RV1_EMPTY) return status;
    destination = status == RV1_EMPTY ? 0u : 1u - selected.bank_index;
    generation = status == RV1_EMPTY ? 1u : selected.generation + 1u;
    status = rv1_encode(bank, generation, scratch, capacity);
    if (status != RV1_OK) return status;
    expected_crc = rv1_crc32(scratch, RV1_FILE_BYTES);
    status = store->write(store->context, rv1_bank_paths[destination], scratch,
                          RV1_FILE_BYTES, &written);
    if (status != RV1_OK) return status;
    if (written != RV1_FILE_BYTES) return RV1_IO;
    status = read_bank(store, destination, scratch, NULL);
    if (status != RV1_OK) return status;
    if (expected_crc != rv1_crc32(scratch, RV1_FILE_BYTES)) return RV1_CORRUPT;
    if (info != NULL) {
        info->bank_index = (uint8_t)destination;
        info->generation = generation;
        info->bank_status[0] = selected.bank_status[0];
        info->bank_status[1] = selected.bank_status[1];
        info->bank_status[destination] = RV1_OK;
    }
    return RV1_OK;
}
