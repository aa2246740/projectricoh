#ifndef GXRCE_H
#define GXRCE_H

#include <stddef.h>
#include <stdint.h>

enum {
    GXRCE_HEADER = 256,
    GXRCE_MAX_FILE = 32768,
    GXRCE_MAX_BSS = 4096,
    GXRCE_SECTIONS = 7,
    GXRCE_MODULES = 3,
    GXRCE_SLOTS = 16,
    GXRCE_HOST_ONLY = 1
};

typedef enum {
    GXRCE_OK = 0,
    GXRCE_ARGUMENT,
    GXRCE_LENGTH,
    GXRCE_VERSION,
    GXRCE_FLAGS,
    GXRCE_CRC,
    GXRCE_LAYOUT,
    GXRCE_BODY_ID,
    GXRCE_RESIDENT_ID,
    GXRCE_MODULE_ID,
    GXRCE_PIN,
    GXRCE_MAP,
    GXRCE_BANK,
    GXRCE_TABLE,
    GXRCE_TWEAK,
    GXRCE_RELOCATION,
    GXRCE_PLACEHOLDER
} GxrceStatus;

typedef struct {
    uint8_t name[8];
    uint16_t main_version, cmp_version;
} GxrceUnit;

typedef struct {
    GxrceUnit unit;
    uint8_t stock_pin[32];
} GxrceModuleTrust;

typedef struct {
    uint8_t body_sha256[32], resident_build_id[32], resident_abi_id[16];
    GxrceModuleTrust modules[GXRCE_MODULES];
} GxrceTrust;

typedef struct { uint32_t offset, length; } GxrceSection;


typedef struct {
    const uint8_t *bytes;
    uint32_t length, build_number, entry_offset, bss_bytes;
    GxrceSection sections[GXRCE_SECTIONS];
    uint8_t selected_module, executable;
} GxrceView;

uint32_t gxrce_crc32(const uint8_t *bytes, size_t length);
void gxrce_sha256(const uint8_t *bytes, size_t length, uint8_t digest[32]);
GxrceStatus gxrce_validate(const uint8_t *bytes, size_t length,
                          const GxrceTrust *trust, const GxrceUnit *connected,
                          unsigned options, GxrceView *out);
const char *gxrce_status_name(GxrceStatus status);

typedef enum {
    GXRCE_UPDATE_KEEP = 0,
    GXRCE_UPDATE_INSTALL = 1,
    GXRCE_UPDATE_CONFLICT = 2
} GxrceUpdate;


GxrceUpdate gxrce_update_decide(const GxrceView *card, const GxrceView *installed);

#endif
