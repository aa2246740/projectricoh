#include "abi.h"
int32_t bv4_native_scope(Bv4Scope *out)
{
    if((bv4_platform.proofs&BV4_REQUIRED_PROOFS)!=BV4_REQUIRED_PROOFS||
       !bv4_platform.boot_probe)return RV4_UNKNOWN;
    return ((int32_t (*)(Bv4Scope *))(uintptr_t)bv4_platform.boot_probe)(out);
}
int32_t bv4_native_lifetime(Bv4Lifetime *out)
{
    if((bv4_platform.proofs&BV4_REQUIRED_PROOFS)!=BV4_REQUIRED_PROOFS||
       !bv4_platform.lifetime_probe)return RV4_UNKNOWN;
    return ((int32_t (*)(Bv4Lifetime *))(uintptr_t)bv4_platform.lifetime_probe)(out);
}
int32_t bv4_invoke_init(uint32_t address,uint32_t base,uint32_t bss,uint32_t bytes)
{
    return ((int32_t (*)(uint32_t,uint32_t,uint32_t,const Bv4Api *))(uintptr_t)address)
        (base,bss,bytes,&bv4_api);
}
int32_t bv4_invoke_hook(uint32_t address,uint32_t hook,uint32_t *frame,uint32_t bss)
{
    return ((int32_t (*)(uint32_t,uint32_t *,uint32_t,const Bv4Api *))(uintptr_t)address)
        (hook,frame,bss,&bv4_api);
}
