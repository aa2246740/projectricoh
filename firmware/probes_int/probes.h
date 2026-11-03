#ifndef PROBES_INT_H
#define PROBES_INT_H
#include "local/upstream/resident_slim/engine_services/engine_services.h"

enum { PV_VERSION=1, PV_ROWS=16, PV_ROW_BYTES=13, PV_GLYPH_BYTES=96,
       PV_MAX_IROM=32768, PV_SMALL_WITNESS=256, PV_LARGE_WITNESS=32768, PV_REAL_WITNESS=65536,
       PV_IMAGE_ENGINE_OFFSET=256, PV_ENTRY_STRIDE=16, PV_PAGE_COUNT=17,
       PV_STATE_MAGIC=0x50563253, PV_UNKNOWN=0xffffffffu };
enum { PV_LIFE=1, PV_NOTICE=2, PV_VIEW=3 };
/* Current resident_impl service profile, not an ABI-h enum. No product write
 * bit is ever requested. Recheck this pin when binding the final resident. */
enum { PV_READY_UI_CAP=1u<<17 };
enum { PV_SELECT_ROW=0x50560001u, PV_SAMPLE=0x50560002u,
       PV_PAGE=0x50560003u, PV_READ_A=0x50560004u, PV_READ_B=0x50560005u,
       PV_MARK=0x50560006u, PV_CAPACITY=0x50560007u };
enum { PV_RO=1, PV_GAPS=2, PV_ERROR=4, PV_LOST=8, PV_PANEL=16 };
enum { PV_HEAP_LOST=1, PV_ROOT_NEW=2, PV_DATA_BAD=4, PV_CODE_BAD=8,
       PV_CANARY_BAD=16, PV_RING_GAP=32, PV_SEQ_GAP=64,
       PV_BINDING_CHANGED=128, PV_COUNTER_END=256, PV_BAD_REPLY=512, PV_CAPACITY_BAD=1024 };
enum { PV_HAVE_UNIT=1, PV_HAVE_SD=2, PV_HAVE_S=4, PV_HAVE_INPUT=8,
       PV_HAVE_REFRESH=16 };
enum { PV_IROM_IDLE, PV_IROM_READ, PV_IROM_MATCH, PV_IROM_UNREFERENCED,
       PV_IROM_FAILED };
enum { PV_STAGE_EPOCHS=1, PV_STAGE_EVENTS=2, PV_STAGE_ALLOC=3,
       PV_STAGE_INSPECT=4, PV_STAGE_UNIT=5, PV_STAGE_SD=6,
       PV_STAGE_SETTINGS=7, PV_STAGE_CAPS=8, PV_STAGE_OPEN=9,
       PV_STAGE_READ=10, PV_STAGE_CLOSE=11, PV_STAGE_LANGUAGE=12,
       PV_STAGE_GLYPH=13, PV_STAGE_BIND=14, PV_STAGE_RELEASE=15,
       PV_STAGE_CAP_ALLOC=16, PV_STAGE_CAP_FREE=17 };

/* Values copied by the resident at a menu-task safe point. No message pointer
 * crosses this boundary. valid_fields identifies which observations exist. */
typedef struct {
    RvBufferHeader header;
    uint32_t valid_fields,sequence,event,source,edge,activity,state;
    uint32_t part,tag,top_tag,top_state,count,view_epoch;
} PvInput;
typedef struct {
    RvBufferHeader header;
    uint32_t valid_fields,sequence,apply_sequence,stage,native_result;
    uint32_t rows_verified,s_published,preview_sequence;
} PvRefresh;

/* Configuration is compiled into the probe, never added to resident ingress. */
#ifndef PV_WITNESS_BYTES
#define PV_WITNESS_BYTES 65536u
#endif
#ifndef PV_REFERENCE_VALID
#define PV_REFERENCE_VALID 0u
#define PV_REFERENCE_REPLICA 0u
#define PV_REFERENCE_BYTES 0u
#define PV_REFERENCE_CRC 0u
#endif
_Static_assert(PV_WITNESS_BYTES==256 || PV_WITNESS_BYTES==32768 ||
               PV_WITNESS_BYTES==65536,"witness tier");

typedef struct {
    uint32_t state,replica,status,native_result,actual,crc,close_status,close_native;
    uint32_t expected_bytes,expected_crc,sd_before,sd_after,reads,epoch;
} PvIrom;
typedef struct {
    uint32_t attempted,allocations,token,address,bytes,nonce,baseline_crc,crc;
    uint32_t baseline_code_crc,code_crc,canary_bad,checks,boot,heap;
} PvWitness;
typedef struct {
    uint32_t state,maximum_bytes,attempted_mask,allocated_mask,freed_mask;
    uint32_t session,sample,boot,heap,witness_bytes;
    uint32_t alloc_status[5],alloc_native[5],free_status[5],free_detail[5];
} PvCapacity;
typedef struct {
    RvBufferHeader header;
    uint32_t first_sequence,last_sequence,dropped,count;
    RvEvent events[RV_RING_COUNT];
} PvEvents;

typedef struct {
    uint32_t magic,context,lease,session,nonce,sample,page,mark,flags,sticky,valid;
    uint32_t last_stage,last_status,last_native,last_detail,boot,heap;
    uint32_t epochs[RV_EPOCH_COUNT],initial_epochs[RV_EPOCH_COUNT];
    uint32_t last_sequence,ring_first,ring_last,dropped,gaps,trace_count;
    RvEvent trace[16];
    uint32_t hook_pre[38],hook_post[38],hook_last_a[38],hook_last_b[38];
    uint32_t sd_epoch,sd_old_epoch,sd_changed,sd_same,sd_status,sd_native,sd_seen;
    uint8_t sd[16],sd_old[16];
    RvUnitInfo unit,unit_old;
    uint32_t unit_changes,unit_same,unit_status,unit_native,unit_seen;
    uint32_t wb0,wb1,wb_old0,wb_old1,wb_changes,s_status,s_native;
    uint32_t panel,ui_view_token,draft[6];
    PvInput input;
    PvRefresh refresh;
    PvIrom irom;
    PvWitness witness;
    PvCapacity capacity[3];
    RvRequest request;
    RvReply reply;
    RvEpochSnapshot epoch_buffer;
    RvLeaseInfo lease_buffer;
    RvSettingsInfo settings_buffer;
    PvEvents event_buffer;
    RvUiList list;
    RvUiText text;
    char rows[PV_ROWS][PV_ROW_BYTES];
    uint8_t glyphs[PV_ROWS][PV_GLYPH_BYTES];
    uint32_t labels[PV_ROWS],table[PV_ROWS],details[PV_ROWS][3];
    uint8_t io[512];
} PvState;

_Static_assert(sizeof(PvInput)==60 && sizeof(PvRefresh)==40,"probe ingress wire");
_Static_assert(sizeof(RvPrivateContext)==120,"resident ingress wire");
_Static_assert(sizeof(PvEvents)==24+16*RV_RING_COUNT,"event buffer wire");
_Static_assert(offsetof(PvState,glyphs)%4==0,"glyph alignment");

int pv_service_allowed(uint32_t,uint32_t);
uint32_t pv_crc32(const void *,uint32_t);
void pv_encode(uint32_t,uint32_t,uint32_t,uint32_t,uint32_t,const uint32_t *,char [16][13]);
int32_t pv_bootstrap(const RvApi *,uint32_t,const RvRequest *,RvReply *);
int32_t pv_init(const RvApi *,uint32_t,const RvRequest *,RvReply *);
int32_t pv_menu_open(const RvApi *,uint32_t,const RvRequest *,RvReply *);
int32_t pv_event(const RvApi *,uint32_t,const RvRequest *,RvReply *);
int32_t pv_panel_open(const RvApi *,uint32_t,const RvRequest *,RvReply *);
int32_t pv_panel_event(const RvApi *,uint32_t,const RvRequest *,RvReply *);
int32_t pv_panel_abort(const RvApi *,uint32_t,const RvRequest *,RvReply *);
int32_t pv_apply_step(const RvApi *,uint32_t,const RvRequest *,RvReply *);
int32_t pv_shutdown(const RvApi *,uint32_t,const RvRequest *,RvReply *);
int32_t pv_abort(const RvApi *,uint32_t,const RvRequest *,RvReply *);

_Static_assert(sizeof(PvState)<=RV_STATE_BYTES,"probe fits resident state");

#ifdef PV_HOST
void *pv_host_pointer(uint32_t,uint32_t);
uint32_t pv_host_address(const void *,uint32_t);
#endif
#endif
