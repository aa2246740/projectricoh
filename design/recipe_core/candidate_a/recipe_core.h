#ifndef GXR_RECIPE_CORE_H
#define GXR_RECIPE_CORE_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

enum {
    RECIPE_SLOT_FIRST = 1,
    RECIPE_SLOT_LAST = 16,
    RECIPE_COLOR_VALUE_COUNT = 13,
    RECIPE_NAME_CAPACITY = 32
};

typedef struct RecipeCore RecipeCore;

/* Slot values are one-based. Every public call rejects values outside 1..16. */
typedef uint8_t RecipeSlot;

/* Encoding is deliberately unspecified until the camera menu encoding is known. */
typedef struct {
    uint8_t length;
    uint8_t bytes[RECIPE_NAME_CAPACITY];
} RecipeName;

/* Synthetic bytes only. Camera ranges and field meanings remain unconfirmed. */
typedef struct {
    uint8_t value[RECIPE_COLOR_VALUE_COUNT];
} RecipeColorValues;

typedef struct {
    RecipeName name;
    RecipeColorValues colors;
} Recipe;

typedef struct {
    RecipeName name;
} RecipeSummary;

typedef enum {
    RECIPE_OK = 0,
    RECIPE_EMPTY,
    RECIPE_CORRUPT,
    RECIPE_IO_ERROR,
    RECIPE_BAD_ARGUMENT,
    RECIPE_BAD_SLOT,
    RECIPE_BAD_NAME
} RecipeStatus;

/*
 * Reads and validates one slot for a menu row. On error, out_summary is
 * unchanged. The core reads no other slot and retains no recipe cache.
 */
RecipeStatus recipe_get_summary(
    RecipeCore *core,
    RecipeSlot slot,
    RecipeSummary *out_summary);

/*
 * Reads one slot. Wrong size, magic, version, embedded slot, reserved bytes,
 * or checksum returns RECIPE_CORRUPT and leaves out_recipe unchanged.
 */
RecipeStatus recipe_load(
    RecipeCore *core,
    RecipeSlot slot,
    Recipe *out_recipe);

/*
 * Deterministically encodes and writes one slot, then reads it back and
 * validates it. No rename, fsync, atomic replacement, or rollback is assumed.
 */
RecipeStatus recipe_save(
    RecipeCore *core,
    RecipeSlot slot,
    const Recipe *recipe);

#ifdef __cplusplus
}
#endif

#endif
