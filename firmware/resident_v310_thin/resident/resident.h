#ifndef RV_SLIM_H
#define RV_SLIM_H
#include "abi.h"
#include "gxrce.h"

typedef struct { uint16_t hook,phase; uint32_t a,b; } RvRingEvent;
typedef struct {
    uint32_t magic;
    uint8_t version,state,inflight,retired7; /* byte 7: retired (v3.8 grain); no reader */
    uint32_t epoch[RV_EPOCH_COUNT];
    uint32_t block,inverse,lease,boot_epoch,heap_epoch,next_token;
    uint32_t rx,event_head,dropped;
    int32_t fault;
    uint32_t heap_begin,heap_end,block_bytes,alloc_bytes;
    uint32_t code_address,code_bytes,code_crc;
    GxrceUnit unit;
    uint32_t ui_block,ui_inverse,ui_alloc_bytes,entry_serial,check_failure;
    uint32_t ui_restore[14],flags;
    RvRingEvent events[RV_RING_COUNT];
    uint32_t lease_inverse;
    /* Last early return. hook | gate<<8 | rv_check reason<<16.
     * gate: 1 disabled, 3 inflight/busy, 4 rv_check, 5 owned.
     * Written only while magic and version match. */
    uint32_t diag_early;
    volatile uint32_t reserved_lane; /* fixed BOOT word, DAT may set dirty/guard */
    uint32_t image_state;
    uint32_t pins[3];
} RvRoot;
_Static_assert(sizeof(RvRoot)==256 && offsetof(RvRoot,events)==216 &&
               offsetof(RvRoot,pins)==244&&offsetof(RvRoot,reserved_lane)==236,"fixed slim root");
enum { BO_PENDING=1,BO_ATTEMPTED=2,BO_DIRTY=4,BO_GUARD=8,RV_BOOT_RUN=0x101 };
enum { RV_ROOT_MAGIC=0x52565333, RV_ROOT_VERSION=32, RV_LEASES=6,
       RV_NATIVE_VIEWS=0x205a279c };
enum { RV_CHECK_ROOT=1,RV_CHECK_SESSION,RV_CHECK_HEAP,RV_CHECK_HEADER,
       RV_CHECK_CODE,RV_CHECK_UNIT,RV_CHECK_UI };
enum { RF_STOP=1,RF_SD=2,RF_UNCERTAIN=4,RF_BUSY=8,RF_OWNER=16,RF_ATTEMPTED=32,RF_QUARANTINE=64,
       RF_PUBLISHED=128 };
enum { RV_SOURCE_NONE,RV_SOURCE_A,RV_SOURCE_B,RV_SOURCE_CARD };
enum { CAP_FILE_WRITE=1u<<16,CAP_UI=1u<<17,CAP_S=1u<<18,CAP_W=1u<<19,CAP_BODY=1u<<20 };
/* image_state: written by the resident only, except that the DAT may store
 * IMG_TOUCHED into it before its first edit of an encoder input that the
 * resident does not put back. IMG_LATCH stays until reboot. H40 reply.detail
 * IMG_REPLY_DONE keeps the DAT's edits. RV_INIT_DONE is the handshake reply
 * detail sent only after the engine's pure init has fully succeeded. */
enum { IMG_IDLE=0,IMG_ENTERED=1,IMG_TOUCHED=2,IMG_DONE=3,IMG_LATCH=0x100,
       IMG_REPLY_DONE=1,RV_INIT_DONE=0x49 };
enum { RV_READ_CAPS=0x7fff, RV_PRODUCT_CAPS=0x1f7fff };
enum { RV_MAX_FILE=98304,RV_MAX_CODE=65536,RV_MAX_IMAGE=114688,
       RV_MAX_LEASE=65536,
       RV_STATE_BYTES=6144,RV_UI_CAPACITY=256 };
/* Native consumers only see this detached snapshot. It is never freed or
 * reused by another engine session, including when its view is buried. */
typedef struct {
    uint8_t state[32],descriptors[72];
    uint32_t details[16][3],labels[16],refs[16];
    uint8_t glyphs[16][96];
    uint32_t magic,inverse;
} RvUiSnapshot;
enum { RV_UI_MAGIC=0x52565533 };
_Static_assert(sizeof(RvUiSnapshot)==1968,"bounded native UI snapshot");
typedef struct { uint8_t body[32],build[32],abi[16]; } RvTrust;
typedef struct { uint32_t valid,generation,bytes,bss; } RvCandidate;
typedef struct { uint32_t token,inverse,base,length,usage; } RvLease;
typedef struct { uint32_t token,fd,epoch,mode; } RvFileToken;

/* This is common engine ingress, not a probe wire layout. The resident owns
 * it for the entire session and passes the same address on every entry. */
typedef struct {
    RvBufferHeader header;
    uint32_t root_address,root_bytes,session_address,session_bytes;
    uint32_t state_address,state_bytes,state_lease;
    uint32_t image_address,image_bytes,image_lease,code_address,code_bytes;
    uint32_t image_bss_bytes,nonce;
    uint32_t ui_state_address,ui_state_bytes,ui_state_capacity;
    uint32_t entries_address,entries_bytes,grain_address,grain_bytes; /* grain_*: unused since v3.9 */
    uint32_t input_fields,input_sequence,input[4],lease_max_bytes;
} RvPrivateContext;
_Static_assert(sizeof(RvPrivateContext)==120,"private context wire");

typedef struct {
    RvEngineEntries entries;
    RvPrivateContext context;
    RvLease leases[RV_LEASES];
    RvFileToken files[2];
    uint32_t image_address,image_bytes,bss_bytes,entry_offset;
    uint32_t selected_source,generation,source_bytes,capabilities;
    uint32_t code_begin,code_end,crc;
    GxrceUnit unit;
    uint32_t settings,settings_bytes,settings_epoch,settings_token;
    uint32_t rpc_token,rpc_phase,bindings[RV_EPOCH_COUNT],sd_id[4];
    uint32_t view_state,view_lease,list,details,rows,cursor,redraw,view_source;
    uint32_t file_bytes[2],file_limit[2],file_object[2],file_end[2];
    RvRequest call_request;RvReply call_reply;
    RvRequest image_request;RvReply image_reply;
    uint32_t k_save[7];
    uint32_t lease_entry[RV_LEASES];
    uint32_t ui_lengths[16],sd_work[4];char paths[2][24];
    uint8_t mark_data[2][128];uint32_t mark_epochs[12],mark_id[4],mark_now[4];
} RvSession;
enum { RV_SESSION_BYTES=(sizeof(RvSession)+3)&~3u,
       RV_BLOCK_OVERHEAD=RV_SESSION_BYTES+RV_STATE_BYTES+RV_UI_CAPACITY,
       RV_MIN_BLOCK_BYTES=RV_BLOCK_OVERHEAD+256,
       RV_MAX_BLOCK_BYTES=RV_BLOCK_OVERHEAD+RV_MAX_IMAGE };
_Static_assert(RV_MAX_BLOCK_BYTES<=131072,"bounded main allocation");
/* File and BSS sizes have already passed rv_header() before these helpers. */
static inline uint32_t rv_image_span(uint32_t file,uint32_t bss)
{return (file+bss+3u)&~3u;}
static inline uint32_t rv_block_bytes(uint32_t file,uint32_t bss)
{return RV_BLOCK_OVERHEAD+rv_image_span(file,bss);}
#ifdef RV_HOST
void *rv_host_address(uint32_t);
#define RV_PTR(a) rv_host_address((uint32_t)(a))
extern RvRoot *rv_host_root;
#else
#define RV_PTR(a) ((void *)(uintptr_t)(a))
#endif
#define RV_WORD(a) (*(volatile uint32_t *)RV_PTR(a))
#define RV_BYTE(a) (*(volatile uint8_t *)RV_PTR(a))
/* Compile the shared root operations into both images, with distinct engine
 * symbols. The service archive has no branch into resident code. */
#ifdef RV_ENGINE_SERVICES
#define rv_clear es_clear
#define rv_equal es_equal
#define rv_crc_update es_crc_update
#define gxrce_crc32 es_crc32
#define rv_be32 es_be32
#ifndef RV_HOST
#define memcpy es_memcpy
#define memset es_memset
#endif
#define rv_session es_session
#define rv_range es_range
#define rv_record es_record
#define rv_ui_abort es_ui_abort
#define rv_free_checked es_free_checked
#define rv_allocation es_allocation
#define rv_ui_snapshot es_ui_snapshot
#define rv_ui_capture es_ui_capture
#endif
static inline int rv_heap_span(uint32_t address,uint32_t n)
{
    uint32_t begin=RV_WORD(0x200d3488),end=RV_WORD(0x200d348c);
    return !(address&3)&&begin<end&&address>=begin&&address<end&&n<=end-address;
}
static inline uint16_t rv_be16(const uint8_t *p) { return (uint16_t)((uint16_t)p[0]<<8|p[1]); }
uint32_t rv_be32(const uint8_t *);
static inline void rv_put32(uint8_t *p,uint32_t v) { p[0]=v>>24;p[1]=v>>16;p[2]=v>>8;p[3]=v; }


void *memcpy(void *,const void *,size_t);
void rv_clear(void *,uint32_t);
int rv_equal(const void *,const void *,uint32_t);
uint32_t rv_crc_update(uint32_t,const uint8_t *,uint32_t);
uint32_t gxrce_crc32(const uint8_t *,size_t);
GxrceStatus rv_header(const uint8_t *,uint32_t,const RvTrust *);
GxrceStatus rv_validate(const uint8_t *,size_t,const RvTrust *,GxrceView *);
/* These readers are used only on the aligned loader workspace and DAT. */
typedef uint32_t RvAligned32 __attribute__((may_alias));
typedef uint16_t RvAligned16 __attribute__((may_alias));
static inline uint32_t rv_aligned32(const uint8_t *p)
{
#ifdef RV_HOST
    return rv_be32(p);
#else
    _Static_assert(__BYTE_ORDER__==__ORDER_BIG_ENDIAN__,"M32R BE reader");
    return *(const RvAligned32 *)(const void *)p;
#endif
}
static inline uint16_t rv_aligned16(const uint8_t *p)
{
#ifdef RV_HOST
    return rv_be16(p);
#else
    return *(const RvAligned16 *)(const void *)p;
#endif
}
GxrceStatus rv_header_aligned(const uint8_t *,uint32_t,const RvTrust *);
GxrceStatus rv_validate_aligned(const uint8_t *,size_t,const RvTrust *,GxrceView *);
int rv_root_valid(RvRoot *);
void rv_reset(RvRoot *);
uint32_t rv_check(RvRoot *);
uint32_t rv_code_guard(uint32_t,uint32_t);
void rv_retire(RvRoot *,uint32_t);
void rv_unit_snapshot(GxrceUnit *);
RvSession *rv_session(RvRoot *);
int rv_allocation(uint32_t,uint32_t,uint32_t);
RvUiSnapshot *rv_ui_snapshot(RvRoot *);
int rv_range(RvRoot *,uint32_t,uint32_t,uint32_t);
void rv_record(RvRoot *,uint32_t,uint32_t,uint32_t,uint32_t);
int32_t rv_ui_abort(RvRoot *);
int rv_ui_capture(RvRoot *,unsigned);
int32_t rv_free_checked(RvRoot *,uint32_t,uint32_t *);
void rv_hook_observe(RvRoot *,uint32_t,uint32_t *);
int32_t rv_load(RvRoot *,const RvTrust *);
int32_t rv_engine(RvRoot *,uint32_t,RvRequest *,RvReply *);
int32_t rv_invoke(uint32_t,const RvApi *,uint32_t,const RvRequest *,RvReply *);
extern const RvTrust rv_trust;
extern const uint32_t rv_pins[3];
int32_t rv_native_open(const char *,uint32_t);
int32_t rv_native_read(int32_t,void *,uint32_t);
int32_t rv_native_close(int32_t);
uint32_t rv_native_alloc(uint32_t);
int32_t rv_native_sd_id(void *);
void rv_native_free(uint32_t);
int32_t rv_native_layer(uint32_t,uint32_t,uint32_t);
int32_t rv_native_rpc_ready(void);
uint32_t rv_irq_save(void);
void rv_irq_restore(uint32_t);
void rv_cache_sync(void);
#endif
