/* Test-only bridge for the frozen r2 host tests. */
#include "kv_math.h"

static struct {
    uint32_t before;
    KvWork work;
    uint32_t after;
} guarded;

int kv_apply(const uint8_t *stock,const uint8_t *base,const KvRequest *request,
             uint8_t *out,KvStats *stats)
{
    int status;
    guarded.before=UINT32_C(0x13579bdf);
    guarded.after=UINT32_C(0x2468ace0);
    status=kv_apply_work(stock,base,request,out,stats,&guarded.work);
    if(guarded.before!=UINT32_C(0x13579bdf) ||
       guarded.after!=UINT32_C(0x2468ace0))__builtin_trap();
    return status;
}
