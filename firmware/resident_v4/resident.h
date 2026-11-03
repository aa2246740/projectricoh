#ifndef RV4_RESIDENT_H
#define RV4_RESIDENT_H
#include "generated/abi.h"

enum { RV4_COLD=0, RV4_LOADING=1, RV4_VALIDATED=2, RV4_READY=3,
       RV4_DISABLED=4, RV4_ROOT_MAGIC=0x52563430u,
       RV4_SNAPSHOT_MAGIC=0x56573430u };
enum { RV4_STOP=1, RV4_ATTEMPTED=2, RV4_RESTORED=4, RV4_HANDLE_UNCERTAIN=8,
       RV4_RESTORING=16, RV4_CONTEXT_PROVEN=1, RV4_UI_PROTOCOL_PROVEN=2,
       RV4_STORAGE_PROTOCOL_PROVEN=4, RV4_RENDER_PROTOCOL_PROVEN=8 };
enum { RV4_UI_NAMES=0x2022f5a8, RV4_UI_ROWS=0x2022f5ac,
       RV4_UI_STATE=0x2022f71c, RV4_UI_MARKER=0x2022f725,
       RV4_UI_CURSOR=0x2022f726, RV4_STOCK_NAMES=0x2022d610,
       RV4_STOCK_DETAILS=0x2023fd38, RV4_VIEWS=0x205a279c,
       RV4_VIEW_ARRAY=0x205a27d8, RV4_VIEW_COUNT=0x205a27d4,
       RV4_ACTIVITY=0x205d9bf8, RV4_STATE=0x205d9c00,
       RV4_PART=0x205a280f, RV4_HEAP_BEGIN=0x200d3488,
       RV4_HEAP_END=0x200d348c, RV4_ALLOC_LIMIT=0x200c0dc4 };

#ifdef RV4_HOST
void *rv4_host_address(uint32_t);
uint32_t rv4_host_pointer(const void *);
#define RV4_PTR(a) rv4_host_address((uint32_t)(a))
#define RV4_ADDRESS(a) rv4_host_pointer(a)
#else
#define RV4_PTR(a) ((void *)(uintptr_t)(a))
#define RV4_ADDRESS(a) ((uint32_t)(uintptr_t)(a))
#endif
#define RV4_WORD(a) (*(volatile uint32_t *)RV4_PTR(a))
#define RV4_BYTE(a) (*(volatile uint8_t *)RV4_PTR(a))
#define RV4_BARRIER() __asm__ __volatile__("" ::: "memory")

typedef struct { uint8_t official[32],build[32],abi[16]; } Rv4Trust;
typedef struct { uint32_t generation,file_bytes,bss_bytes,code_offset,code_bytes,reloc_offset,reloc_count,capabilities,required_events; uint32_t entries[16]; } Rv4Validated;
/* Catalog order is H01,H02,H05..V34,R35..R38; no duplicate id per site. */
typedef struct { uint32_t address; } Rv4HookMetadata;
typedef struct {
    uint8_t state[32],descriptors[72];
    uint32_t details[16][3],labels[16],refs[16];
    uint8_t glyphs[16][96];
    uint32_t magic,ticket,generation,inverse;
} Rv4Snapshot;
_Static_assert(sizeof(Rv4Snapshot)<=RV4_MAX_SNAPSHOT,"bounded snapshot");
typedef struct { uint16_t version,bytes; uint32_t rows,cursor,generation; uint8_t glyphs[16][96]; } Rv4ViewInput;
typedef struct { uint32_t context_probe,proof_flags,ui_owner,task8_owner; } Rv4NativeProfile;
extern const Rv4Trust rv4_trust;
extern const uint32_t rv4_pins[3];
extern const Rv4NativeProfile rv4_native_profile;
extern const Rv4HookMetadata rv4_hook_metadata[36];
extern const uint8_t rv4_blank_details[192];

void *memcpy(void *,const void *,size_t);
void rv4_clear(void *,uint32_t);
int rv4_equal(const void *,const void *,uint32_t);
uint16_t rv4_be16(const uint8_t *);
uint32_t rv4_be32(const uint8_t *);
void rv4_put32(uint8_t *,uint32_t);
uint32_t rv4_crc_update(uint32_t,const uint8_t *,uint32_t);
uint32_t rv4_crc(const uint8_t *,uint32_t);
int32_t rv4_header(const uint8_t *,uint32_t,const Rv4Trust *,Rv4Validated *);
int32_t rv4_validate(const uint8_t *,uint32_t,const Rv4Trust *,Rv4Validated *);
int rv4_span(uint32_t,uint32_t,uint32_t,uint32_t);
int rv4_allocation(uint32_t,uint32_t,uint32_t);
int rv4_root_valid(const Rv4Root *);
int32_t rv4_cold_init(Rv4Root *);
int32_t rv4_binding(Rv4Root *);
int32_t rv4_invalidate(Rv4Root *,uint32_t);
void rv4_retire(Rv4Root *,int32_t);
int32_t rv4_call(Rv4Root *,uint32_t,uint32_t,const Rv4Event *,Rv4Reply *);
int rv4_event_identity(const Rv4Root *,const Rv4Event *,uint32_t,uint32_t);
int32_t rv4_load(Rv4Root *,const Rv4Trust *);
int32_t rv4_host_call(uint32_t,uint32_t,const Rv4Event *,Rv4Reply *);
int32_t rv4_dispatch(Rv4Root *,uint32_t,const Rv4Event *,Rv4Reply *);
uint32_t rv4_protect(const Rv4Root *,uint32_t);
int32_t rv4_view_publish(Rv4Root *,const Rv4ViewInput *,uint32_t *);
int32_t rv4_view_withdraw(Rv4Root *,uint32_t);
int32_t rv4_view_draw(Rv4Root *,uint32_t,uint32_t);
int32_t rv4_ui_mutation(Rv4Root *,uint32_t);
uint32_t rv4_details(Rv4Root *,uint32_t);
void rv4_ui_drain(Rv4Root *);
int32_t rv4_constructor(Rv4Root *,uint32_t);
int32_t rv4_storage_scope(Rv4Root *);
int32_t rv4_unavailable_gate(Rv4Root *,uint32_t,uint32_t);
void rv4_hook_observe(Rv4Root *,uint32_t,uint32_t *);

uint32_t rv4_irq_save(void);
void rv4_irq_restore(uint32_t);
void rv4_cache_sync(void);
uint32_t rv4_native_context(void);
void rv4_native_unit(uint32_t [3]);
int32_t rv4_native_open(const char *,uint32_t);
int32_t rv4_native_read(int32_t,void *,uint32_t);
int32_t rv4_native_close(int32_t);
uint32_t rv4_native_alloc(uint32_t);
void rv4_native_free(uint32_t);
int32_t rv4_native_sd_id(void *);
int32_t rv4_native_draw(uint32_t,uint32_t,uint32_t);
int32_t rv4_native_layer(uint32_t,uint32_t,uint32_t);
int32_t rv4_invoke(uint32_t,const Rv4HostApi *,uint32_t,const Rv4Event *,Rv4Reply *);
#endif
