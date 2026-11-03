#ifndef RV_IMPL_H
#define RV_IMPL_H
#include "abi.h"
#include "../card_container/gxrce.h"
typedef struct { uint32_t token,fd,epoch,mode; } RvFileToken;
typedef struct {
    uint32_t magic,version,state,capabilities,epoch[RV_EPOCH_COUNT];
    uint32_t image_address,image_bytes,bss_bytes,entry_offset;
    uint32_t lease,inflight,owner,busy;
    uint32_t event_head,dropped,fault,selected_source,generation,source_bytes;
    uint32_t post[8],ui_restore[8];
    RvFileToken files[2];
    uint32_t flags[8],reserved[2];
    RvEvent events[16];
} RvRoot;
_Static_assert(sizeof(RvRoot)==512 && offsetof(RvRoot,events)==256,"root layout");
enum { RV_ROOT_MAGIC=0x52563252, RV_LEASES=6 };
enum { F_BOOT,F_HEAP,F_STOP,F_RX,F_SD,F_UNCERTAIN,F_NEXT,F_GRAIN };
enum { RV_SOURCE_NONE,RV_SOURCE_A,RV_SOURCE_B,RV_SOURCE_CARD };
enum { CAP_FILE_WRITE=1u<<16,CAP_UI=1u<<17,CAP_S=1u<<18,CAP_W=1u<<19 };
enum { RV_READ_CAPS=0x7fff, RV_PRODUCT_CAPS=0xe7fff };
typedef struct { uint8_t body[32],build[32],abi[16]; uint32_t pins[3]; } RvTrust;
enum { RV_MAX_FILE=49152,RV_MAX_CODE=24576,RV_MAX_IMAGE=57344 };
typedef struct { uint32_t valid,generation,bytes,crc; } RvCandidate;
typedef struct { uint32_t token,inverse,base,length,usage; } RvLease;
/* Engine-local init payload; abi.h remains byte-for-byte frozen. */
typedef struct {
    RvBufferHeader header;
    uint32_t image_address,image_bytes,grain_address,grain_bytes;
    uint8_t wb_binding[12];
} RvInitWire;
_Static_assert(sizeof(RvInitWire)==36,"engine init payload");
typedef struct {
    RvLease leases[RV_LEASES];
    RvEngineEntries entries;
    RvInitWire init_wire;
    GxrceUnit unit;
    uint32_t code_begin,code_end,crc,settings,settings_bytes,settings_epoch,settings_token;
    uint32_t rpc_token,rpc_phase,bindings[4],sd_id[4];
    uint32_t view_state,view_lease,list,details,rows,cursor,redraw;
    uint32_t file_bytes[2],file_limit[2],file_object[2];
} RvSession;
enum { RV_IMAGE_BYTES=RV_MAX_IMAGE,
       RV_BLOCK_BYTES=((sizeof(RvSession)+3)&~3u)+RV_IMAGE_BYTES };
#ifdef RV_HOST
void *rv_host_address(uint32_t);
#define RV_PTR(a) rv_host_address((uint32_t)(a))
extern RvRoot *rv_host_root;
#else
#define RV_PTR(a) ((void *)(uintptr_t)(a))
#endif
#define RV_WORD(a) (*(volatile uint32_t *)RV_PTR(a))
#define RV_BYTE(a) (*(volatile uint8_t *)RV_PTR(a))
static inline int rv_heap_span(uint32_t address,uint32_t n)
{
    uint32_t begin=RV_WORD(0x200d3488),end=RV_WORD(0x200d348c);
    return !(address&3)&&begin<end&&address>=begin&&address<=end&&n<=end-address;
}
static inline uint16_t rv_be16(const uint8_t *p) { return (uint16_t)((uint16_t)p[0]<<8|p[1]); }
static inline uint32_t rv_be32(const uint8_t *p) { return (uint32_t)p[0]<<24|(uint32_t)p[1]<<16|(uint32_t)p[2]<<8|p[3]; }
static inline void rv_put32(uint8_t *p,uint32_t v) { p[0]=v>>24;p[1]=v>>16;p[2]=v>>8;p[3]=v; }
void *memcpy(void *,const void *,size_t);
void rv_clear(void *,uint32_t);
int rv_equal(const void *,const void *,uint32_t);
uint32_t rv_crc_update(uint32_t,const uint8_t *,uint32_t);
uint32_t gxrce_crc32(const uint8_t *,size_t);
GxrceStatus rv_validate(const uint8_t *,size_t,const RvTrust *,GxrceView *);
void rv_reset(RvRoot *);
void rv_record(RvRoot *,uint32_t,uint32_t,uint32_t,uint32_t);
void rv_notify(RvRoot *,uint32_t,uint32_t,int32_t);
void rv_hook_observe(RvRoot *,uint32_t,uint32_t *);
void rv_ui_abort(RvRoot *);
void rv_grain(RvRoot *,uint8_t *);
void rv_grain_commit(RvRoot *,uint32_t,uint32_t);
int32_t rv_choose(const RvCandidate[3]);
int32_t rv_load(RvRoot *,const RvTrust *,const GxrceUnit *);
int32_t rv_service(RvRoot *,uint32_t,uint32_t,const RvRequest *,RvReply *);
int32_t rv_call(uint32_t,uint32_t,const RvRequest *,RvReply *);
RvSession *rv_session(RvRoot *);
int rv_range(RvRoot *,uint32_t,uint32_t,uint32_t);
int32_t rv_engine(RvRoot *,uint32_t,RvRequest *,RvReply *);
int32_t rv_invoke(uint32_t,const RvApi *,uint32_t,const RvRequest *,RvReply *);
int32_t rv_unit(RvRoot *,GxrceUnit *);
void rv_epochs(RvRoot *,uint32_t);
extern const RvApi rv_api;
extern const RvTrust rv_trust;
int32_t rv_native_open(const char *,uint32_t);
int32_t rv_native_create(const char *,uint32_t);
int32_t rv_native_read(int32_t,void *,uint32_t);
int32_t rv_native_write(int32_t,const void *,uint32_t);
int32_t rv_native_close(int32_t);
int32_t rv_native_delete(const char *);
int32_t rv_native_rename(const char *,const char *);
uint32_t rv_native_alloc(uint32_t);
int32_t rv_native_free(uint32_t);
int32_t rv_native_context(void);
uint32_t rv_native_unit(uint32_t);
int32_t rv_native_sd_id(void *);
int32_t rv_native_rpc_ready(void);
int32_t rv_native_rpc_limit(void);
int32_t rv_rpc8_native(uint32_t,uint32_t);
int32_t rv_native_preview(uint32_t);
int32_t rv_native_language(void);
int32_t rv_native_ascii(const char *,uint32_t,void *,uint32_t);
int32_t rv_native_layer(uint32_t,uint32_t,uint32_t);
int32_t rv_native_draw(uint32_t,uint32_t,uint32_t);
uint32_t rv_irq_save(void);
void rv_irq_restore(uint32_t);
void rv_cache_sync(void);
#endif
