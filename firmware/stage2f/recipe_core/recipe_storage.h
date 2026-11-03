#ifndef PROJECTRICOH_RECIPE_STORAGE_H
#define PROJECTRICOH_RECIPE_STORAGE_H

#include "recipe_core.h"

#include <stddef.h>
#include <stdint.h>

enum { RECIPE_RECORD_SIZE = 64 };

typedef enum {
    RECIPE_STORE_OK = 0,
    RECIPE_STORE_MISSING,
    RECIPE_STORE_IO
} RecipeStoreStatus;

typedef RecipeStoreStatus (*RecipeStoreRead)(
    void *context,
    RecipeSlot slot,
    uint8_t *record,
    size_t capacity,
    size_t *actual_length);

typedef RecipeStoreStatus (*RecipeStoreWrite)(
    void *context,
    RecipeSlot slot,
    const uint8_t *record,
    size_t length,
    size_t *written_length);

typedef RecipeStoreStatus (*RecipeStoreRemove)(void *context, RecipeSlot slot);

typedef struct {
    void *context;
    RecipeStoreRead read;
    RecipeStoreWrite write;
    RecipeStoreRemove remove;
} RecipeStorage;

struct RecipeCore {
    RecipeStorage storage;
};

#endif
