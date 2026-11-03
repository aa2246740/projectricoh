#ifndef RV2_ABI_H
#define RV2_ABI_H
#include <stdint.h>
#include <stddef.h>

enum { RV_BASE=0x2005276c, RV_LIMIT=0x20054800, RV_ROOT=0x20054700,
       RV_CAPACITY=8340, RV_ROOT_BYTES=256, RV_RING_COUNT=8,
       RV_ABI_VERSION=1, RV_REQ_BYTES=64, RV_REPLY_BYTES=32 };
enum RvResult { RV_PASS=0, RV_CONSUMED=1, RV_CLOSE_AND_PASS=2, RV_FAULT=3 };
enum RvStatus { RV_OK=0, RV_EOF=1, RV_UNAVAILABLE=2, RV_IO=-1,
    RV_BUSY=-2, RV_ARGUMENT=-3, RV_UNSUPPORTED=-4, RV_STALE=-5,
    RV_VERIFY=-6, RV_CONFLICT=-7, RV_UNCERTAIN=-8,
    RV_OWNER=-9, RV_RANGE=-10, RV_FAULTED=-11, RV_CAPABILITY=-12 };
enum RvService { RV_STORAGE=1, RV_LEASE=2, RV_CACHE=3, RV_RPC8=4,
    RV_PREVIEW=5, RV_SETTINGS=6, RV_UNIT=7, RV_SD_ID=8, RV_EPOCHS=9,
    RV_UI_LIST=10, RV_UI_TEXT=11, RV_UI_VIEW=12, RV_EVENTS=13,
    RV_QUERY=14, RV_CRC32=15, RV_SHA256=16 };
enum RvEpoch { RV_BOOT_E, RV_HEAP_E, RV_LINK_E, RV_UNIT_E, RV_SD_E,
    RV_IROM_E, RV_VIEW_E, RV_S_E, RV_MODE_E, RV_SEG_E, RV_POWER_E, RV_IO_E,
    RV_EPOCH_COUNT };
enum RvState { RV_FACTORY, RV_LOADING, RV_VALIDATED, RV_READY, RV_FENCED, RV_FAILED };

typedef struct {
    uint16_t version, bytes;
    uint32_t flags, args[14];
} RvRequest;
typedef struct {
    uint16_t version, bytes;
    int32_t status, native_result;
    uint32_t actual, token, epoch, capabilities, detail;
} RvReply;
typedef struct {
    uint32_t sequence;
    uint16_t hook, phase;
    uint32_t a, b;
} RvEvent;
typedef int32_t (*RvCall)(uint32_t service, uint32_t operation,
                         const RvRequest *, RvReply *);
typedef struct { uint16_t id, request_bytes; uint32_t operations; } RvServiceDesc;
typedef struct {
    uint16_t version, bytes;
    uint32_t service_count, capabilities, root_bytes;
    RvCall call;
    uint32_t reserved[3];
    RvServiceDesc services[16];
} RvApi;

/* Entry offsets are relative to the whole validated container, never pointers
 * returned by an unvalidated engine. All entry calls use four GCC arguments. */
typedef int32_t (*RvEngineEntry)(const RvApi *, uint32_t context,
                                const RvRequest *, RvReply *);
typedef struct {
    uint16_t version, bytes;
    uint32_t init, menu_open, event, panel_open, panel_event, panel_abort;
    uint32_t apply_step, shutdown, abort;
} RvEngineEntries;
typedef struct { uint32_t param_id; int32_t value; } RvParamEdit;

/* Indirect request/reply buffers. All addresses and leases are explicit;
 * no native compiler pointer or size_t occurs in these wire layouts. */
typedef struct { uint16_t version,bytes; uint32_t flags; } RvBufferHeader;
typedef struct {
    RvBufferHeader header;
    uint32_t token,base,length,usage,boot_epoch,heap_epoch;
} RvLeaseInfo;
typedef struct {
    RvBufferHeader header;
    uint32_t token,address,length,settings_epoch;
} RvSettingsInfo;
typedef struct { uint16_t offset; uint8_t value,reserved; } RvSettingsWrite;
typedef struct {
    RvBufferHeader header;
    uint32_t settings_token,count;
    RvSettingsWrite writes[16];
} RvSettingsPlan;
typedef struct {
    RvBufferHeader header;
    uint8_t name[8];
    uint16_t main_version,cmp_version;
    uint32_t unit_epoch,link_epoch,rx_sequence,valid;
} RvUnitInfo;
typedef struct {
    RvBufferHeader header;
    uint32_t session_token,epochs[12];
} RvEpochSnapshot;
typedef struct {
    RvBufferHeader header;
    uint32_t view_token,state_address,state_bytes,rows,cursor;
    uint32_t label_table,details,lease_token;
} RvUiList;
typedef struct {
    RvBufferHeader header;
    uint32_t source_address,source_bytes,source_lease;
    uint32_t glyph_address,glyph_capacity,glyph_lease,language,actual_bytes;
} RvUiText;
typedef struct {
    RvBufferHeader header;
    uint32_t view_token,part,tag,state_address,state_bytes,lease_token;
    uint32_t expected_array,expected_count,expected_top_tag,expected_top_state;
} RvUiView;
typedef struct {
    RvBufferHeader header;
    uint32_t first_sequence,last_sequence,dropped,count;
    RvEvent events[];
} RvEventSnapshot;
typedef struct {
    RvBufferHeader header;
    uint32_t service_count,capabilities,root_bytes,api_address;
    uint8_t resident_build_id[32],resident_abi_id[16];
} RvApiInfo;
typedef struct {
    RvBufferHeader header;
    uint32_t source_address,source_bytes,source_lease;
    uint32_t digest_address,digest_bytes,digest_lease;
} RvHashRequest;

_Static_assert(sizeof(RvRequest)==64, "request wire size");
_Static_assert(sizeof(RvReply)==32, "reply wire size");
_Static_assert(sizeof(RvEvent)==16, "event wire size");
_Static_assert(sizeof(RvEngineEntries)==40, "entry wire size");
_Static_assert(sizeof(RvParamEdit)==8, "generic parameter edit");
_Static_assert(sizeof(RvLeaseInfo)==32 && sizeof(RvSettingsInfo)==24, "lease and S layout");
_Static_assert(sizeof(RvSettingsPlan)==80 && sizeof(RvUnitInfo)==36, "S plan and unit layout");
_Static_assert(sizeof(RvEpochSnapshot)==60 && sizeof(RvUiList)==40, "epochs and UI list layout");
_Static_assert(sizeof(RvUiText)==40 && sizeof(RvUiView)==48, "UI text and view layout");
_Static_assert(sizeof(RvEventSnapshot)==24 && sizeof(RvApiInfo)==72, "snapshot layouts");
_Static_assert(sizeof(RvHashRequest)==32, "SHA request layout");
_Static_assert(offsetof(RvReply,status)==4 && offsetof(RvReply,detail)==28, "reply offsets");
#endif
