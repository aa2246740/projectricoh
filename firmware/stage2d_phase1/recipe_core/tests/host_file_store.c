#include "host_file_store.h"

#include <errno.h>
#include <stdio.h>

enum { HOST_PATH_CAPACITY = 1024 };

static RecipeStoreStatus make_path(
    const HostFileStore *store,
    RecipeSlot slot,
    char *path,
    size_t capacity)
{
    int length = snprintf(
        path,
        capacity,
        "%s/slot-%02u.rcp",
        store->directory,
        (unsigned)slot.one_based);

    if (length < 0 || (size_t)length >= capacity) {
        return RECIPE_STORE_IO;
    }
    return RECIPE_STORE_OK;
}

static RecipeStoreStatus host_read(
    void *context,
    RecipeSlot slot,
    uint8_t *record,
    size_t capacity,
    size_t *actual_length)
{
    HostFileStore *store = context;
    char path[HOST_PATH_CAPACITY];
    FILE *file;
    long file_length;
    size_t copy_length;
    size_t read_length;
    int read_failed;
    int close_result;

    if (make_path(store, slot, path, sizeof(path)) != RECIPE_STORE_OK) {
        return RECIPE_STORE_IO;
    }
    file = fopen(path, "rb");
    if (file == NULL) {
        return errno == ENOENT ? RECIPE_STORE_MISSING : RECIPE_STORE_IO;
    }
    if (fseek(file, 0, SEEK_END) != 0) {
        (void)fclose(file);
        return RECIPE_STORE_IO;
    }
    file_length = ftell(file);
    if (file_length < 0 || fseek(file, 0, SEEK_SET) != 0) {
        (void)fclose(file);
        return RECIPE_STORE_IO;
    }

    *actual_length = (size_t)file_length;
    copy_length = *actual_length < capacity ? *actual_length : capacity;
    read_length = fread(record, 1, copy_length, file);
    read_failed = ferror(file);
    close_result = fclose(file);
    if (read_length != copy_length || read_failed != 0 || close_result != 0) {
        return RECIPE_STORE_IO;
    }
    return RECIPE_STORE_OK;
}

static RecipeStoreStatus host_write(
    void *context,
    RecipeSlot slot,
    const uint8_t *record,
    size_t length,
    size_t *written_length)
{
    HostFileStore *store = context;
    char path[HOST_PATH_CAPACITY];
    FILE *file;
    int write_failed;
    int close_result;

    if (make_path(store, slot, path, sizeof(path)) != RECIPE_STORE_OK) {
        return RECIPE_STORE_IO;
    }
    file = fopen(path, "wb");
    if (file == NULL) {
        return RECIPE_STORE_IO;
    }
    *written_length = fwrite(record, 1, length, file);
    write_failed = ferror(file);
    close_result = fclose(file);
    if (write_failed != 0 || close_result != 0) {
        return RECIPE_STORE_IO;
    }
    return RECIPE_STORE_OK;
}

static RecipeStoreStatus host_remove(void *context, RecipeSlot slot)
{
    HostFileStore *store = context;
    char path[HOST_PATH_CAPACITY];

    if (make_path(store, slot, path, sizeof(path)) != RECIPE_STORE_OK) {
        return RECIPE_STORE_IO;
    }
    if (remove(path) == 0) {
        return RECIPE_STORE_OK;
    }
    return errno == ENOENT ? RECIPE_STORE_MISSING : RECIPE_STORE_IO;
}

RecipeStorage host_file_storage(HostFileStore *store)
{
    RecipeStorage storage;

    storage.context = store;
    storage.read = host_read;
    storage.write = host_write;
    storage.remove = host_remove;
    return storage;
}
