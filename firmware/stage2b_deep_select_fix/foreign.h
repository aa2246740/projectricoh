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

/* One out-of-line copy. Acquire must call it; inlining the same compare
 * twice blew the payload reserve. The activity compare stays addi r5,#-8. */
uint32_t rfw_ui_active(void);
#endif
