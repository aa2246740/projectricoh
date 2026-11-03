#ifndef GXRCE2_H
#define GXRCE2_H
#include <stddef.h>
#include <stdint.h>

enum { GXR2_HEADER=256, GXR2_MAX_FILE=32768, GXR2_MAX_BSS=4096,
       GXR2_SECTIONS=7, GXR2_MODULES=3, GXR2_SLOTS=16, GXR2_HOST_ONLY=1,
       GXR2_DESCRIPTOR=16, GXR2_PARAM_MAX=32 };
typedef enum {
    GXR2_OK, GXR2_ARGUMENT, GXR2_LENGTH, GXR2_VERSION, GXR2_FLAGS,
    GXR2_CRC, GXR2_LAYOUT, GXR2_BODY_ID, GXR2_RESIDENT_ID, GXR2_MODULE_ID,
    GXR2_PIN, GXR2_MAP, GXR2_BANK, GXR2_TABLE, GXR2_TWEAK,
    GXR2_RELOCATION, GXR2_PLACEHOLDER
} Gxr2Status;
typedef struct { uint8_t name[8]; uint16_t main_version,cmp_version; } Gxr2Unit;
typedef struct { Gxr2Unit unit; uint32_t stock_crc32; uint8_t stock_sha256[32]; } Gxr2ModuleTrust;
typedef struct {
    uint8_t body_sha256[32],resident_build_id[32],resident_abi_id[16];
    Gxr2ModuleTrust modules[3];
} Gxr2Trust;
typedef struct { uint32_t offset,length; } Gxr2Section;
typedef struct {
    const uint8_t *bytes;
    uint32_t length,build_number,entry_offset,bss_bytes;
    Gxr2Section sections[7];
    uint16_t param_slots,record_bytes;
    uint8_t selected_module,executable,semantic;
} Gxr2View;
typedef struct { const uint8_t *bytes; uint16_t length; } Gxr2Row;

uint32_t gxr2_crc32(const uint8_t *, size_t);
void gxr2_sha256(const uint8_t *, size_t, uint8_t [32]);
/* No allocation, libc, I/O, relocation or writes to input. Failure leaves out
 * unchanged. Trust is supplied independently of the container. */
Gxr2Status gxr2_gate_validate(const uint8_t *, size_t, const Gxr2Trust *,
                            const Gxr2Unit *, unsigned, Gxr2View *out);
/* Only accepts a private view returned by gate_validate. The data sections and
 * header must remain unchanged. Engine relocation is allowed between layers;
 * this call deliberately does not recheck engine CRC or patch words. Pure init
 * gets no native write or UI capability. */
Gxr2Status gxr2_semantic_validate(const Gxr2View *, const Gxr2Trust *, Gxr2View *out);
Gxr2Status gxr2_validate(const uint8_t *, size_t, const Gxr2Trust *,
                       const Gxr2Unit *, unsigned, Gxr2View *out);
/* Accessors require a semantic view. module=0..2, slot=1..16, row=0..7.
 * Slot expansion reconstructs the byte-identical legacy 448 B representation,
 * retaining the referenced descriptor owner's identity for explicit aliases. */
Gxr2Status gxr2_row(const Gxr2View *, unsigned module, unsigned slot, unsigned row, Gxr2Row *);
Gxr2Status gxr2_expand(const Gxr2View *, unsigned module, unsigned slot, uint8_t [448]);
Gxr2Status gxr2_parameter(const Gxr2View *, unsigned module, unsigned slot,
                        uint32_t id, int32_t *lo, int32_t *hi, int32_t *def);
const char *gxr2_status_name(Gxr2Status);
enum { GXR2_KEEP, GXR2_INSTALL, GXR2_CONFLICT };
int gxr2_update_decide(const Gxr2View *, const Gxr2View *);
#endif
