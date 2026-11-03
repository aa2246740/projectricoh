#include "resident.h"

static void clear(void *p, size_t n)
{ uint8_t *b=p; while (n--) *b++=0; }

void rv_reset(RvRoot *r)
{
    clear(r,sizeof(*r));
    r->magic=RV_ROOT_MAGIC; r->version=1; r->epoch[RV_BOOT_E]=1;
}

void rv_record(RvRoot *r, uint32_t hook, uint32_t phase, uint32_t a, uint32_t b)
{
    uint32_t psw=rv_irq_save(), seq=r->event_head+1;
    RvEvent *e;
    if (seq==0) { r->state=RV_FENCED; r->fault=RV_RANGE; rv_irq_restore(psw); return; }
    e=&r->events[(seq-1)&15];
    e->hook=(uint16_t)hook; e->phase=(uint16_t)phase; e->a=a; e->b=b;
    __asm__ __volatile__("" ::: "memory");
    e->sequence=seq; r->event_head=seq;
    if (seq>16) ++r->dropped;
    rv_irq_restore(psw);
}

/* Observer skeleton: every thunk still replays the official instruction.
 * Post-return wrappers, fences and engine dispatch are specified, not enabled. */
void rv_hook_observe(RvRoot *r, uint32_t hook, const uint32_t *frame)
{
    if (r->magic!=RV_ROOT_MAGIC || r->version!=1) rv_reset(r);
    rv_record(r,hook,0,hook==10 ? frame[4] : frame[11],frame[10]);
}

static int same(const RvCandidate *a, const RvCandidate *b)
{
    unsigned i;
    if (a->bytes!=b->bytes) return 0;
    for (i=0;i<32;++i) if (a->digest[i]!=b->digest[i]) return 0;
    return 1;
}

int32_t rv_choose(const RvCandidate c[3])
{
    int32_t best=-1;
    unsigned i;
    for (i=0;i<2;++i) if (c[i].valid) {
        if (best<0 || c[i].generation>c[best].generation) best=(int32_t)i;
        else if (c[i].generation==c[best].generation && !same(&c[i],&c[best])) {
            /* Equal-generation IROM conflict: only a strictly newer card
             * resolves it. Never pick a lower/equal card arbitrarily. */
            return c[2].valid && c[2].generation>c[i].generation ? 2 : RV_CONFLICT;
        }
    }
    if (c[2].valid && (best<0 || c[2].generation>c[best].generation)) return 2;
    return best;
}

static int32_t read_one(const char *path, uint8_t *p, uint32_t cap, uint32_t *length)
{
    int32_t fd=rv_native_open(path,0), n, result=RV_OK;
    uint8_t tail;
    *length=0;
    if (fd==-1) return RV_IO;
    while (*length<cap) {
        n=rv_native_read(fd,p+*length,cap-*length);
        if (n<0 || (uint32_t)n>cap-*length) { result=RV_IO; break; }
        if (n==0) break;
        *length+=(uint32_t)n;
    }
    if (result==RV_OK && *length==cap && rv_native_read(fd,&tail,1)!=0) result=RV_IO;
    if (rv_native_close(fd)!=0) result=RV_IO;
    return result;
}

int32_t rv_load(RvRoot *r, uint8_t *work, uint32_t cap,
                const GxrceTrust *trust, const GxrceUnit *unit)
{
    static const char paths[3][18]={"/IROM/GXRCE0.DAT","/IROM/GXRCE1.DAT","/ATA1/GXRCE.DAT"};
    RvCandidate candidates[3];
    GxrceView v;
    uint32_t length, i;
    int32_t selected;
    if (!work || cap<GXRCE_MAX_FILE || !trust || !unit) return RV_ARGUMENT;
    if (r->busy || r->inflight) return RV_BUSY;
    clear(candidates,sizeof(candidates));
    r->busy=1; r->state=RV_LOADING;
    for (i=0;i<3;++i) {
        if (read_one(paths[i],work,GXRCE_MAX_FILE,&length)!=RV_OK ||
            rv_validate(work,length,trust,unit,&v)!=GXRCE_OK) continue;
        candidates[i].valid=1; candidates[i].generation=v.build_number;
        candidates[i].bytes=length; gxrce_sha256(work,length,candidates[i].digest);
    }
    selected=rv_choose(candidates);
    if (selected>=0 && selected<2 && candidates[2].valid &&
        candidates[2].generation==candidates[selected].generation &&
        !same(&candidates[2],&candidates[selected])) r->fault=(uint32_t)RV_CONFLICT;
    if (selected<0 || read_one(paths[selected],work,GXRCE_MAX_FILE,&length)!=RV_OK ||
        rv_validate(work,length,trust,unit,&v)!=GXRCE_OK) goto fail;
    {
        uint8_t digest[32];
        gxrce_sha256(work,length,digest);
        if (length!=candidates[selected].bytes) goto fail;
        for (i=0;i<32;++i) if (digest[i]!=candidates[selected].digest[i]) goto fail;
        for (i=0;i<32;++i) r->source_sha[i]=digest[i];
    }
    r->selected_source=(uint32_t)selected+1; r->generation=v.build_number;
    r->source_bytes=length; r->entry_offset=v.entry_offset; r->bss_bytes=v.bss_bytes;
    r->state=RV_VALIDATED; r->busy=0;
    /* Deliberately no relocation, native UI writes, engine execution, install
     * or READY publication. The caller owns the measurement buffer. */
    return RV_OK;
fail:
    r->selected_source=RV_SOURCE_NONE; r->state=RV_FACTORY; r->busy=0;
    return selected==RV_CONFLICT ? RV_CONFLICT : RV_VERIFY;
}

int32_t rv_service(RvRoot *r, uint32_t id, uint32_t op, const RvRequest *q, RvReply *p)
{
    int32_t status=RV_UNSUPPORTED;
    if (!q || !p || q->version!=1 || q->bytes!=64 || q->flags) return RV_ARGUMENT;
    clear(p,sizeof(*p)); p->version=1; p->bytes=32;
    if (id==RV_QUERY && op==0) { p->actual=16; status=RV_OK; }
    if (id==RV_EPOCHS && op<RV_EPOCH_COUNT) { p->epoch=r->epoch[op]; status=RV_OK; }
    /* Write capabilities remain zero, including installed-marker rename.
     * Reserved service IDs return UNSUPPORTED rather than a null function. */
    p->status=status;
    return status;
}

int32_t rv_call(uint32_t id, uint32_t op, const RvRequest *q, RvReply *p)
{ return rv_service((RvRoot *)(uintptr_t)RV_ROOT,id,op,q,p); }

#define DESC(i) {i,64,0}
const RvApi rv_api={1,sizeof(RvApi),16,0,512,rv_call,{0,0,0},
    {DESC(1),DESC(2),DESC(3),DESC(4),DESC(5),DESC(6),DESC(7),DESC(8),
     DESC(9),DESC(10),DESC(11),DESC(12),DESC(13),DESC(14),DESC(15),DESC(16)}};
