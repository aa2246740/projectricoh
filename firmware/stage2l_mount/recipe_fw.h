#ifndef RECIPE_FW_H
#define RECIPE_FW_H
#include "recipe_v1/recipe_v1.h"
#include "foreign.h"
#include "deep_isp.h"

typedef const uint8_t *const *RfwLabelRef;
typedef RfwLabelRef const *RfwLabelTable;
enum { RFW_GLYPH_BYTES = 96 };

typedef struct {
    /* Keep the allocation reachable through the ADJ descriptor after closing.
     * Native drawing may retain these label addresses beyond a close event. */
    RfwLabelRef table[RV1_SLOT_COUNT];
    const uint8_t *labels[RV1_SLOT_COUNT];
    uint8_t glyphs[RV1_SLOT_COUNT][RFW_GLYPH_BYTES];
    Rv1Bank bank;
    uint8_t scratch[RV1_FILE_BYTES];
    Rv1Status load_status, last_status;
    uint8_t busy, opened, applied_slot;
    uint8_t pending_slot;
    RfwDeepState deep;
} RfwCache;

extern const RfwLabelRef rfw_closed_table[RV1_SLOT_COUNT];
extern const RfwLabelRef rfw_empty_table[RV1_SLOT_COUNT];
extern const uint32_t rfw_no_details[RV1_SLOT_COUNT][3];
extern const Rv1Store rfw_store;
#ifdef RECIPE_FW_HOST
RfwLabelTable volatile *rfw_binding(void);
#else
static inline RfwLabelTable volatile *rfw_binding(void)
{ return (RfwLabelTable volatile *)(uintptr_t)0x2022f5a8; }
#endif

Rv1Status rfw_read_file(void *, const char *, uint8_t *, size_t, size_t *);
Rv1Status rfw_write_file(void *, const char *, const uint8_t *, size_t, size_t *);
Rv1Status rfw_acquire(void *, volatile uint8_t **, size_t *);
Rv1Status rfw_request_preview(void *);
void rfw_release(void *, int);
uint32_t rfw_open(void);
void rfw_close(void);
uint32_t rfw_is_open(void);
uint32_t rfw_is_active(void);
Rv1Status rfw_select(uint32_t);
uint32_t rfw_cursor_commit(void);
uint32_t rfw_apply_action(uint32_t);
#endif
