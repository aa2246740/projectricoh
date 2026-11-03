#include "resident.h"
int32_t rv4_storage_scope(Rv4Root *r)
{
    uint32_t task;
    if(!rv4_root_valid(r))return RV4_ARGUMENT;
    if(!(rv4_native_profile.proof_flags&RV4_STORAGE_PROTOCOL_PROVEN))return RV4_UNKNOWN;
    task=rv4_native_context();
    if(!task||task!=rv4_native_profile.task8_owner||task!=r->job.owner||!r->job.id||
       !r->job.grant||r->job.pin!=1||r->job.phase!=1||r->job.cancel||
       r->job.generation!=r->epochs[RV4_E_JOB]||r->job.media_epoch!=r->epochs[RV4_E_MEDIA]||
       r->job.heap_epoch!=r->epochs[RV4_E_HEAP]||r->job.unit_epoch!=r->epochs[RV4_E_UNIT]||
       (r->header.flags&(RV4_STOP|RV4_HANDLE_UNCERTAIN)))return RV4_STALE;
    return RV4_OK;
}
int32_t rv4_unavailable_gate(Rv4Root *r,uint32_t kind,uint32_t generation)
{
    if(!rv4_root_valid(r)||kind>2)return RV4_ARGUMENT;
    if(generation!=r->epochs[kind==0?RV4_E_BOOT:kind==1?RV4_E_CAPTURE:RV4_E_RENDER])return RV4_STALE;
    /* No task-8 grants, boot retries, capture pins or rendering are issued here. */
    return RV4_UNSUPPORTED;
}
