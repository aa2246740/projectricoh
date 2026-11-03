#ifndef PN_STORE_H
#define PN_STORE_H
#include "panel_port.h"
#include "eng_core_contract.h"

enum { PS_ENGINE=1, PS_TWEAK=2, PS_CARD=1, PS_A=2, PS_B=3,
       PS_TEMP=4, PS_DELIVERED=5, PS_MAX_ENGINE=32768, PS_MAX_TWEAK=256 };
enum { PS_READ_CARD=1, PS_READ_IROM=2, PS_WRITE=4, PS_RENAME=8,
       PS_DELETE=16, PS_MARK=32 };
typedef enum {
    PS_IDLE, PS_SCANNING, PS_WRITING, PS_TEMP_CHECK, PS_RENAMING,
    PS_FINAL_CHECK, PS_SAVED, PS_ACKING, PS_DONE, PS_COMMIT_UNCERTAIN
} PsStage;
typedef struct { uint8_t kind, unit, slot; } PsObject;
typedef struct { uint32_t generation, bytes, crc32; } PsInfo;
typedef struct {
    uint8_t replica, valid, observed;
    PsInfo info;
} PsCandidate;
/* verify must validate the complete format, CRC, identities, metadata and all
 * expected layout/version bindings. crc32 is a full-file CRC32. Equal-generation
 * candidates also receive a byte-for-byte comparison, so CRC collisions do not
 * make different candidates equivalent. No SHA implementation runs here. */
typedef int32_t (*PsVerify)(void *, const PsObject *, const uint8_t *, uint32_t,
                            PsInfo *);
typedef struct {
    PnPort *port;
    uint8_t *work;
    uint32_t capacity, epoch, caps;
    uint8_t busy, uncertain;
    PsStage stage;
    PsVerify verify;
    void *verify_context;
    uint8_t chunk[512];
} PsStore;
typedef struct {
    uint8_t installed, delivered, replica;
    int32_t save_status, delivery_status;
} PsInstallResult;

void ps_init(PsStore *, PnPort *, uint8_t *, uint32_t, PsVerify, void *);
/* Engine candidate loader for host/bootstrap integration. GXTS uses gxts_load. */
int32_t ps_load(PsStore *, const PsObject *, uint8_t *out, uint32_t capacity,
                uint32_t *bytes, PsCandidate *);
/* raw is the accepted, immutable, UNRELOCATED original disk container. */
int32_t ps_install(PsStore *, const uint8_t *raw, uint32_t, PsInstallResult *);

/* Private fixed-object operations used by the GxtsIO adapter. They retain the
 * resident wire contract, capability checks, token revocation and uncertainty. */
int32_t ps_fixed_begin(PsStore *, const PsObject *, int writing);
int32_t ps_fixed_end(PsStore *, int32_t);
int32_t ps_fixed_open(PsStore *, const PsObject *, unsigned replica, int writing,
                       uint32_t preserve, uint32_t bytes, uint32_t *token);
int32_t ps_fixed_transfer(PsStore *, unsigned op, uint32_t token, void *,
                           uint32_t bytes, uint32_t *actual);
int32_t ps_fixed_close(PsStore *, uint32_t token);
int32_t ps_fixed_remove(PsStore *, const PsObject *, unsigned replica, uint32_t preserve);
int32_t ps_fixed_rename(PsStore *, const PsObject *, unsigned target, uint32_t preserve);
#endif
