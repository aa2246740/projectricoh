#ifndef GXR_RECIPE_V1_H
#define GXR_RECIPE_V1_H

#include <stddef.h>
#include <stdint.h>

enum {
    RV1_SLOT_COUNT = 16,
    RV1_NAME_BYTES = 32,
    RV1_COLOR_BYTES = 13,
    RV1_RECORD_BYTES = 64,
    RV1_HEADER_BYTES = 32,
    RV1_FILE_BYTES = RV1_HEADER_BYTES + RV1_SLOT_COUNT * RV1_RECORD_BYTES,
    RV1_SETTINGS_MIN_BYTES = 0x8b6,
    RV1_SELECTOR_OFFSET = 0x36e,
    RV1_SELECTOR_SETTING1 = 0x04,
    RV1_BASE_STANDARD = 0x01,
    RV1_BASE_COLOR = 0x04,
    RV1_BASE_BW = 0x03,
    RV1_BASE_BW_TE = 0x06,
    RV1_WB0_OFFSET = 0x6dd,
    RV1_WB1_OFFSET = 0x6de
};

typedef enum {
    RV1_OK = 0,
    RV1_ARGUMENT,
    RV1_RANGE,
    RV1_LENGTH,
    RV1_CORRUPT,
    RV1_VERSION,
    RV1_EMPTY,
    RV1_NO_CARD,
    RV1_READ_ONLY,
    RV1_FULL,
    RV1_IO,
    RV1_CONFLICT
} Rv1Status;

/* base_mode tags raw[]: color uses all 13 bytes; BW uses C/S then zeroes;
 * TE uses C/S/V/tone then zeroes. Native tone values are 1,2,3,4,6.
 * Color order: C/S/V, saturation[O/G/B/R/M], hue[O/G/B/R/M].
 * wb[] is signed compensation -8..+8, not the S encoding 1..17.
 */
typedef struct {
    uint8_t name_length;
    uint8_t name[RV1_NAME_BYTES];
    uint8_t base_mode;
    uint8_t raw[RV1_COLOR_BYTES];
    int8_t wb[2];
} Rv1Recipe;

typedef struct {
    uint8_t occupied;
    Rv1Recipe recipe;
} Rv1Slot;

typedef struct {
    uint32_t generation;
    Rv1Slot slots[RV1_SLOT_COUNT];
} Rv1Bank;

uint32_t rv1_crc32(const uint8_t *bytes, size_t length);
Rv1Status rv1_validate_recipe(const Rv1Recipe *recipe);
void rv1_bank_init(Rv1Bank *bank);
/* Input and output buffers must not overlap. Errors leave outputs unchanged.
 * decode(out=NULL) validates the whole file and optionally returns generation.
 */
Rv1Status rv1_encode(const Rv1Bank *bank, uint32_t generation,
                     uint8_t *file, size_t capacity);
Rv1Status rv1_decode(const uint8_t *file, size_t length,
                     Rv1Bank *out, uint32_t *generation);
/* Explicit import of a validated legacy v1 bank as color. No name inference.
 * Normal decode/encode and the camera store accept/write v2 only.
 */
Rv1Status rv1_import_v1(const uint8_t *file, size_t length, Rv1Bank *out);

typedef struct { uint16_t offset; uint8_t value; } Rv1Write;
typedef struct { Rv1Write writes[16]; uint8_t count; } Rv1WritePlan;
Rv1Status rv1_plan(const Rv1Recipe *recipe, Rv1WritePlan *plan);

/* EMPTY means file absent. NO_CARD is distinct. Report actual length, including
 * oversized files, and include close/flush errors in the returned status.
 * A failing write may damage its destination. The other bank must be intact.
 * The caller serializes the entire load/save transaction against other writers.
 */
typedef struct {
    void *context;
    Rv1Status (*read)(void *context, const char *path, uint8_t *bytes,
                      size_t capacity, size_t *actual);
    Rv1Status (*write)(void *context, const char *path, const uint8_t *bytes,
                       size_t length, size_t *actual);
} Rv1Store;

typedef struct {
    uint32_t generation;
    uint8_t bank_index;
    Rv1Status bank_status[2];
} Rv1StoreInfo;

extern const char rv1_bank_paths[2][19];
/* scratch is caller-owned, at least RV1_FILE_BYTES; it cannot overlap out/bank.
 * These routines never delete a bank and never call camera flash functions.
 */
Rv1Status rv1_store_load(const Rv1Store *store, uint8_t *scratch,
                         size_t capacity, Rv1Bank *out, Rv1StoreInfo *info);
Rv1Status rv1_store_save(const Rv1Store *store, uint8_t *scratch,
                         size_t capacity, const Rv1Bank *bank,
                         Rv1StoreInfo *info);

/* acquire resolves the current S object and prevents shooting, native edits,
 * MY recall and persistence from racing with the mode's writes and preview.
 * request_preview must synchronously bridge to 0x202d6f38 with native r4=0,
 * requesting command 0x2f03, while that ownership is held. It must not re-enter
 * apply. Use task serialization, not an interrupt-disabled firmware call.
 * Map native return 0 to RV1_OK and -1 to RV1_IO. A preview error leaves the
 * complete recipe in S; there is no rollback or preservation of old Setting1.
 * release only releases ownership; changed=1 means the writes and request ran.
 * RV1_OK does not prove the module accepted or rendered the preview request.
 */
typedef struct {
    void *context;
    Rv1Status (*acquire)(void *context, volatile uint8_t **settings, size_t *length);
    Rv1Status (*request_preview)(void *context);
    void (*release)(void *context, int changed);
} Rv1SettingsPort;

/* Overwrite only the chosen mode's native fields, WB, then publish selector.
 * Color uses Setting1; BW uses 645/646; TE uses 641/642/644/643. There is no
 * backup or restore: native whole-S persistence can retain the selected values.
 * Errors before the preview request leave S unchanged.
 */
Rv1Status rv1_apply(const Rv1SettingsPort *port, const Rv1Recipe *recipe);

#endif
