#ifndef RV2_RESIDENT_H
#define RV2_RESIDENT_H
#include "abi.h"
#include "../card_container/gxrce.h"
typedef struct { uint32_t token, fd, epoch, mode; } RvFileToken;
typedef struct {
    uint32_t magic, version, state, capabilities;
    uint32_t epoch[RV_EPOCH_COUNT];
    uint32_t image_address, image_bytes, bss_bytes, entry_offset;
    uint32_t lease, inflight, owner, busy;
    uint32_t event_head, dropped, fault, selected_source;
    uint32_t generation, source_bytes;
    uint8_t source_sha[32];
    uint32_t ui_restore[8];
    RvFileToken files[2];
    uint32_t flags[8], reserved[2];
    RvEvent events[RV_RING_COUNT];
} RvRoot;
_Static_assert(sizeof(RvRoot)==512, "root size");
_Static_assert(offsetof(RvRoot,events)==256, "ring offset");

enum { RV_ROOT_MAGIC=0x52563252 };
enum RvSource { RV_SOURCE_NONE, RV_SOURCE_A, RV_SOURCE_B, RV_SOURCE_CARD };
typedef struct {
    uint32_t valid, generation, bytes;
    uint8_t digest[32];
} RvCandidate;

void rv_reset(RvRoot *);
void rv_record(RvRoot *, uint32_t hook, uint32_t phase, uint32_t a, uint32_t b);
void rv_hook_observe(RvRoot *, uint32_t hook, const uint32_t *frame);
int32_t rv_choose(const RvCandidate candidates[3]);
GxrceStatus rv_validate(const uint8_t *, size_t, const GxrceTrust *, const GxrceUnit *, GxrceView *);
int32_t rv_load(RvRoot *, uint8_t *, uint32_t, const GxrceTrust *, const GxrceUnit *);
int32_t rv_service(RvRoot *, uint32_t, uint32_t, const RvRequest *, RvReply *);
int32_t rv_call(uint32_t, uint32_t, const RvRequest *, RvReply *);
extern const RvApi rv_api;
extern const GxrceTrust rv_trust;

int32_t rv_native_open(const char *, uint32_t);
int32_t rv_native_read(int32_t, void *, uint32_t);
int32_t rv_native_close(int32_t);
uint32_t rv_irq_save(void);
void rv_irq_restore(uint32_t);
void rv_cache_sync(void);
#endif
