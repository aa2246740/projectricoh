#ifndef PROJECTRICOH_RECIPE_CORE_H
#define PROJECTRICOH_RECIPE_CORE_H

/*
 * DESIGN SKETCH ONLY — declarations have no implementation in this candidate.
 *
 * This is a host-C format for synthetic test data. "RCPBHOST" is a new
 * project magic, not a Ricoh .IFO marker or a camera-compatible format.
 */

#include <stddef.h>
#include <stdint.h>

#define RECIPE_LIBRARY_BYTES       1024u
#define RECIPE_LIBRARY_WORK_BYTES  1024u
#define RECIPE_SLOT_COUNT            16u
#define RECIPE_COLOR_COUNT           13u
#define RECIPE_NAME_CAPACITY         32u

typedef struct RecipeSlot {
    uint8_t one_based; /* Valid values are 1..16. */
} RecipeSlot;

/*
 * Opaque encoded values for the 13 Image Settings fields.
 * Their camera addresses, signedness, range, and ABI are still unknown.
 */
typedef struct RecipeColors {
    uint8_t bytes[RECIPE_COLOR_COUNT];
} RecipeColors;

typedef struct Recipe {
    uint8_t name_length;
    uint8_t name_utf8[RECIPE_NAME_CAPACITY];
    RecipeColors colors;
} Recipe;

typedef uint8_t RecipeMutationKind;
enum {
    RECIPE_MUTATION_REPLACE = 1u,
    RECIPE_MUTATION_DELETE = 2u
};

typedef struct RecipeMutation {
    RecipeMutationKind kind;
    RecipeSlot slot;
    Recipe replacement; /* Ignored for DELETE. */
} RecipeMutation;

/* Caller-owned fixed workspace. Its representation is private to the core. */
typedef struct RecipeLibrary {
    uint8_t opaque[RECIPE_LIBRARY_WORK_BYTES];
} RecipeLibrary;

typedef enum RecipeStatus {
    RECIPE_STATUS_OK = 0,
    RECIPE_STATUS_EMPTY = 1,
    RECIPE_STATUS_BAD_ARGUMENT = -1,
    RECIPE_STATUS_BAD_LENGTH = -2,
    RECIPE_STATUS_BAD_MAGIC = -3,
    RECIPE_STATUS_UNSUPPORTED_VERSION = -4,
    RECIPE_STATUS_BAD_LAYOUT = -5,
    RECIPE_STATUS_BAD_CHECKSUM = -6,
    RECIPE_STATUS_BAD_SLOT = -7,
    RECIPE_STATUS_BAD_NAME = -8,
    RECIPE_STATUS_BAD_RECORD = -9
} RecipeStatus;

/*
 * Load and validate one complete library image. encoded_length == 0 creates a
 * canonical empty library and requires encoded == NULL. Any nonzero input must
 * be exactly RECIPE_LIBRARY_BYTES. No input pointer is retained.
 * On failure, the prior library state is unchanged.
 *
 * NOT IMPLEMENTED in this candidate.
 */
RecipeStatus recipe_library_load(
    RecipeLibrary *library,
    const uint8_t *encoded,
    size_t encoded_length);

/*
 * Read one directly addressed slot. EMPTY is distinct from corrupt input.
 * On EMPTY or error, out_recipe is zeroed. No camera state is accepted.
 *
 * NOT IMPLEMENTED in this candidate.
 */
RecipeStatus recipe_library_read(
    const RecipeLibrary *library,
    RecipeSlot slot,
    Recipe *out_recipe);

/*
 * Apply REPLACE or DELETE and emit the entire canonical library image.
 * Replacing with identical data and deleting an empty slot are idempotent.
 * On success, library and out_encoded describe the same state. This function
 * does not write files and makes no rename, fsync, or transaction guarantee.
 * An invalid mutation changes neither library nor out_encoded.
 *
 * NOT IMPLEMENTED in this candidate.
 */
RecipeStatus recipe_library_apply(
    RecipeLibrary *library,
    const RecipeMutation *mutation,
    uint8_t out_encoded[RECIPE_LIBRARY_BYTES]);

#if defined(__STDC_VERSION__) && __STDC_VERSION__ >= 201112L
_Static_assert(sizeof(RecipeColors) == 13u, "RecipeColors budget changed");
_Static_assert(sizeof(Recipe) == 46u, "Recipe budget changed");
_Static_assert(sizeof(RecipeMutation) == 48u, "RecipeMutation budget changed");
_Static_assert(sizeof(RecipeLibrary) == 1024u, "RecipeLibrary budget changed");
#endif

#endif /* PROJECTRICOH_RECIPE_CORE_H */
