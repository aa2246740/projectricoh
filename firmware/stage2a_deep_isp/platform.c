#include "recipe_fw.h"

static int bank_path(const char *path)
{
    unsigned i, j;
    if (path == NULL) return 0;
    for (i = 0; i < 2; ++i) {
        for (j = 0; j < sizeof(rv1_bank_paths[i]); ++j) {
            if (path[j] != rv1_bank_paths[i][j]) break;
            if (path[j] == 0) return 1;
        }
    }
    return 0;
}

Rv1Status rfw_read_file(void *context, const char *path, uint8_t *bytes,
                        size_t capacity, size_t *actual)
{
    int32_t handle, count, closed;
    uint8_t extra;
    Rv1Status status = RV1_OK;
    (void)context;
    if (!bank_path(path) || bytes == NULL || actual == NULL ||
        capacity != RV1_FILE_BYTES) return RV1_ARGUMENT;
    *actual = 0;
    if (*rfw_word(0x200d8080) == 0) return RV1_NO_CARD;
    handle = gxr_open(path, 0);
    /* No errno mapping has been proven. In particular -1 is not EMPTY. */
    if (handle == -1) return RV1_IO;
    while (*actual < capacity) {
        count = gxr_read(handle, bytes + *actual, (uint32_t)(capacity - *actual));
        if (count < 0 || (uint32_t)count > capacity - *actual) {
            status = RV1_IO;
            break;
        }
        if (count == 0) break;
        *actual += (uint32_t)count;
    }
    if (status == RV1_OK && *actual == capacity) {
        count = gxr_read(handle, &extra, 1);
        if (count < 0 || count > 1) status = RV1_IO;
        else *actual += (uint32_t)count;
    }
    closed = gxr_close(handle);
    if (closed == -1) status = RV1_IO;
    return status;
}

#ifdef RECIPE_FW_HOST
Rv1Status rfw_write_file(void *context, const char *path, const uint8_t *bytes,
                         size_t length, size_t *actual)
{
    int32_t handle, count, closed;
    Rv1Status status = RV1_OK;
    (void)context;
    if (!bank_path(path) || bytes == NULL || actual == NULL ||
        length != RV1_FILE_BYTES) return RV1_ARGUMENT;
    *actual = 0;
    if (*rfw_word(0x200d8080) == 0) return RV1_NO_CARD;
    if (*rfw_word(0x200d8084) != 0) return RV1_READ_ONLY;
    /* The v1 caller selects the other bank. Never delete the selected bank.
     * Unknown deletion failures cannot authorize creation or truncation. */
    if (gxr_delete(path) == -1) return RV1_IO;
    handle = gxr_create(path, 2);
    if (handle == -1) return RV1_IO;
    while (*actual < length) {
        count = gxr_write(handle, bytes + *actual, (uint32_t)(length - *actual));
        if (count <= 0 || (uint32_t)count > length - *actual) {
            status = RV1_IO;
            break;
        }
        *actual += (uint32_t)count;
    }
    closed = gxr_close(handle);
    if (closed == -1) status = RV1_IO;
    return status;
}

const Rv1Store rfw_store = { NULL, rfw_read_file, rfw_write_file };
#endif

Rv1Status rfw_acquire(void *context, volatile uint8_t **settings, size_t *length)
{
    RfwCache *cache = context;
    Rv1Status status;
    /* 202738ac reads this same category cell. Exclude scene/movie categories
     * before publishing any settings. The existing native ADJ activity gates
     * remain intact; busy is only our own reentrancy guard, not an OS lock. */
    if (cache->busy || !rfw_ui_active() || *rfw_byte(0x205d9a7f) != 0)
        return RV1_CONFLICT;
    /* Resolve both cells each time: MY recall can replace S. */
    *settings = rfw_settings();
    *length = *rfw_word(0x200c0db0);
    if (*settings == NULL || *length < RV1_SETTINGS_MIN_BYTES) return RV1_LENGTH;
    cache->busy = 1;
    if (cache->pending_slot != 0) {
        status = rfw_deep_transition(&cache->deep,
            &cache->bank.slots[cache->pending_slot - 1].recipe);
        if (status != RV1_OK) {
            cache->busy = 0;
            return status;
        }
    }
    return RV1_OK;
}

Rv1Status rfw_request_preview(void *context)
{
    (void)context;
    return gxr_preview(0) == 0 ? RV1_OK : RV1_IO;
}

void rfw_release(void *context, int changed)
{
    (void)changed;
    ((RfwCache *)context)->busy = 0;
}
