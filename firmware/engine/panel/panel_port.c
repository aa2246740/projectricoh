#include "panel_port.h"
#include <limits.h>

void pn_zero(void *p, uint32_t n)
{ uint8_t *d=p; while (n--) *d++=0; }
void pn_copy(void *d, const void *s, uint32_t n)
{ uint8_t *a=d; const uint8_t *b=s; while (n--) *a++=*b++; }
int pn_equal(const void *a, const void *b, uint32_t n)
{ const uint8_t *x=a,*y=b; while (n--) if (*x++!=*y++) return 0; return 1; }

uint32_t pn_address(PnPort *p, const void *s, uint32_t n)
{
    if (!s || !n) return 0;
    if (p->address) return p->address(p->address_context,s,n);
#if UINTPTR_MAX > UINT32_MAX
    return 0; /* Host tests must supply an address mapper; never truncate. */
#else
    if ((uintptr_t)s > UINT32_MAX-(n-1)) return 0;
    return (uint32_t)(uintptr_t)s;
#endif
}

void pn_request(PnPort *p, RvRequest *q, uint32_t lease)
{
    unsigned i;
    pn_zero(q,sizeof(*q)); q->version=1; q->bytes=sizeof(*q);
    q->args[0]=p->context; q->args[1]=lease;
    for (i=0;i<6;i++) q->args[2+i]=p->epochs[i];
}

int32_t pn_call(PnPort *p, uint32_t service, uint32_t op,
                const RvRequest *q, RvReply *r)
{
    const RvApi *a=p->api;
    unsigned i;
    int32_t status;
    pn_zero(r,sizeof(*r));
    if (!a || !a->call || a->version!=1 || a->service_count>16 ||
        a->bytes<offsetof(RvApi,services)+a->service_count*sizeof(RvServiceDesc))
        return RV_UNSUPPORTED;
    for (i=0;i<a->service_count;i++) if (a->services[i].id==service) break;
    if (i==a->service_count || op>=32 ||
        a->services[i].request_bytes!=sizeof(*q) ||
        !(a->services[i].operations&(UINT32_C(1)<<op))) return RV_UNSUPPORTED;
    r->version=1; r->bytes=sizeof(*r);
    status=a->call(service,op,q,r);
    if (r->version!=1 || r->bytes!=sizeof(*r) || status!=r->status)
        return RV_VERIFY;
    return status;
}
