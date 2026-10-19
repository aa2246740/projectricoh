#ifndef RECIPE_FW_FOREIGN_H
#define RECIPE_FW_FOREIGN_H
#include <stddef.h>
#include <stdint.h>

/* These symbols have the GCC ABI. abi.S is the only caller of ROM addresses. */
int32_t gxr_open(const char *, uint32_t);
int32_t gxr_create(const char *, uint32_t);
int32_t gxr_read(int32_t, void *, uint32_t);
int32_t gxr_write(int32_t, const void *, uint32_t);
int32_t gxr_close(int32_t);
int32_t gxr_delete(const char *);
int32_t gxr_mkdir(const char *);
void *gxr_alloc(uint32_t);
int32_t gxr_preview(uint32_t);
void gxr_draw_text(uint32_t, const void *);
void gxr_ascii(const char *, uint32_t, uint8_t *, uint32_t);
uint32_t gxr_language(void);
int32_t gxr_layer_action(uint32_t, uint32_t, uint32_t);

typedef struct {
    uint8_t tag, reserved[3];
    uint32_t state;
} RfwUiEntry;

#ifdef RECIPE_FW_HOST
volatile uint32_t *rfw_word(uint32_t);
volatile uint8_t *rfw_byte(uint32_t);
volatile uint8_t *rfw_settings(void);
const volatile RfwUiEntry *rfw_ui_entries(void);
uintptr_t rfw_heap_begin(void);
uintptr_t rfw_heap_end(void);
#else
static inline volatile uint32_t *rfw_word(uint32_t address)
{ return (volatile uint32_t *)(uintptr_t)address; }
static inline volatile uint8_t *rfw_byte(uint32_t address)
{ return (volatile uint8_t *)(uintptr_t)address; }
static inline volatile uint8_t *rfw_settings(void)
{ return (volatile uint8_t *)(uintptr_t)*rfw_word(0x200c0dac); }
static inline const volatile RfwUiEntry *rfw_ui_entries(void)
{ return (const volatile RfwUiEntry *)(uintptr_t)*rfw_word(0x205a27d8); }
/* The native allocator initializes these bounds at 2005bf00; its free
 * routine checks the same cells before reading a block header. */
static inline uintptr_t rfw_heap_begin(void)
{ return *rfw_word(0x200d3488); }
static inline uintptr_t rfw_heap_end(void)
{ return *rfw_word(0x200d348c); }
#endif

static inline uint32_t rfw_ui_active(void)
{
    uint32_t count = *rfw_byte(0x205a27d4);
    const volatile RfwUiEntry *entries;
    /* 201c0840..201c0890 owns the part2 stack: count +8, entries +12,
     * eight-byte entries containing tag +0 and state pointer +4. */
    if (*rfw_byte(0x205a280f) != 2 || count == 0 || count > 2 ||
        *rfw_byte(0x2022f71c) != 5) return 0;
    entries = rfw_ui_entries();
    if (entries == NULL) return 0;
    return entries[count - 1].tag == 33 &&
        entries[count - 1].state == UINT32_C(0x2022f71c);
}
#endif
