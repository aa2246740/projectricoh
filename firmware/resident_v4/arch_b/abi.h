#ifndef RV4_ARCH_B_ABI_H
#define RV4_ARCH_B_ABI_H
#include "../resident.h"

/* Bootstrap ABI 1, separate from the DAT v4 wire ABI. All addresses are u32. */
enum {
    BV4_MAGIC=0x42345631u, BV4_HEADER_BYTES=160, BV4_MAX_FILE=65536,
    BV4_MAX_BSS=16384, BV4_MAX_RELOCATIONS=1024,
    BV4_LOADING=1, BV4_READY=2, BV4_DISABLED=3,
    BV4_EVER_ENTERED=1, BV4_EVER_READY=2, BV4_HANDLE_UNCERTAIN=4,
    BV4_FACTORY=8, BV4_QUARANTINED=16, BV4_SCOPE_LOST=32,
    BV4_PROOF_BOOT_BARRIER=1, BV4_PROOF_HEAP_LIFETIME=2,
    BV4_PROOF_FILE_SCOPE=4, BV4_PROOF_CACHE=8,
    BV4_REQUIRED_PROOFS=15, BV4_BOOT_PHASE=1
};
typedef struct {
    uint32_t boot_instance,heap_epoch,owner,phase,mount_epoch,proofs,reserved0,reserved1;
} Bv4Scope;
typedef struct { uint32_t boot_instance,heap_epoch,heap_begin,heap_end; } Bv4Lifetime;
typedef struct {
    uint8_t official[32],window_build[32],abi[16];
    uint8_t approved_file_sha256[32];
    uint32_t pin_enabled;
} Bv4Trust;
typedef struct { uint32_t proofs,boot_probe,lifetime_probe,reserved; } Bv4Platform;
typedef struct { uint32_t major,bytes,root_address,required_proofs; } Bv4Api;
typedef struct {
    uint32_t file_bytes,bss_bytes,code_offset,code_bytes,init_offset,hook_offset;
    uint32_t reloc_offset,reloc_count;
} Bv4Validated;
typedef struct {
    uint32_t magic,state,flags,fault;
    Bv4Scope scope;
    uint32_t heap_begin,heap_end,base,inverse,alloc_bytes,file_bytes,bss_bytes;
    uint32_t code_offset,code_bytes,init_offset,hook_offset,active_calls,serial;
    uint8_t code_sha256[32],extension_id[16];
    uint32_t reserved[91];
} Bv4Root;
_Static_assert(sizeof(Bv4Root)==512,"bootstrap root is 512B");
_Static_assert(sizeof(Bv4Trust)==116,"trust pin layout");
_Static_assert(sizeof(Bv4Scope)==32,"boot scope layout");
_Static_assert(sizeof(Bv4Api)==16,"bootstrap API layout");

extern const Bv4Trust bv4_trust;
extern const Bv4Platform bv4_platform;
extern const Bv4Api bv4_api;
extern const uint8_t bv4_blank_details[192];
void bv4_sha256(const uint8_t *,uint32_t,uint8_t [32]);
int32_t bv4_header(const uint8_t *,Bv4Validated *);
int32_t bv4_relocate(uint8_t *,uint32_t,const Bv4Validated *);
int32_t bv4_native_scope(Bv4Scope *);
int32_t bv4_native_lifetime(Bv4Lifetime *);
int32_t bv4_invoke_init(uint32_t,uint32_t,uint32_t,uint32_t);
int32_t bv4_invoke_hook(uint32_t,uint32_t,uint32_t *,uint32_t);
int32_t bv4_boot(Bv4Root *);
void bv4_hook_observe(Bv4Root *,uint32_t,uint32_t *);
void bv4_emergency(uint32_t,uint32_t *);
#endif
