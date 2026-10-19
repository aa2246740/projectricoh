#ifndef PROJECTRICOH_RECIPE_CORE_H
#define PROJECTRICOH_RECIPE_CORE_H

#include <stdint.h>

enum {
    RECIPE_SLOT_FIRST = 1,
    RECIPE_SLOT_LAST = 16,
    RECIPE_COLOR_VALUE_COUNT = 13,
    RECIPE_NAME_CAPACITY = 32
};

typedef struct RecipeCore RecipeCore;

typedef struct {
    uint8_t one_based;
} RecipeSlot;

/* The camera's character encoding is not yet mapped. */
typedef struct {
    uint8_t length;
    uint8_t bytes[RECIPE_NAME_CAPACITY];
} RecipeName;

/* These are opaque prototype values, not confirmed camera field encodings. */
typedef struct {
    uint8_t bytes[RECIPE_COLOR_VALUE_COUNT];
} RecipeColors;

typedef struct {
    RecipeName name;
    RecipeColors colors;
} Recipe;

typedef enum {
    RECIPE_OK = 0,
    RECIPE_EMPTY,
    RECIPE_CORRUPT,
    RECIPE_IO_ERROR,
    RECIPE_BAD_ARGUMENT,
    RECIPE_BAD_SLOT,
    RECIPE_BAD_NAME
} RecipeStatus;

/* Errors and empty slots leave the caller's output unchanged. */
RecipeStatus recipe_read(RecipeCore *core, RecipeSlot slot, Recipe *out_recipe);

/* Writes one slot, then reads it back. Power-loss recovery is not assumed. */
RecipeStatus recipe_save(RecipeCore *core, RecipeSlot slot, const Recipe *recipe);

/* Removal is explicit; passing NULL to save can never erase a slot. */
RecipeStatus recipe_delete(RecipeCore *core, RecipeSlot slot);

#if defined(__STDC_VERSION__) && __STDC_VERSION__ >= 201112L
_Static_assert(sizeof(RecipeColors) == 13, "Color-only result must remain 13 bytes");
_Static_assert(sizeof(Recipe) == 46, "Recipe memory budget changed");
#endif

#endif
