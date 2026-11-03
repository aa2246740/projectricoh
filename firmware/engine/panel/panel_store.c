#include "panel_store.h"
#include <limits.h>

static int object_ok(const PsObject *o)
{
    return o && ((o->kind==PS_ENGINE && !o->unit && !o->slot) ||
        (o->kind==PS_TWEAK && o->unit>=1 && o->unit<=3 && o->slot<16));
}
static uint32_t limit(const PsObject *o)
{ return o->kind==PS_ENGINE ? PS_MAX_ENGINE : PS_MAX_TWEAK; }
static int32_t fence(PsStore *s)
{ s->uncertain=1; s->stage=PS_COMMIT_UNCERTAIN; return RV_UNCERTAIN; }

static void request(PsStore *s, const PsObject *o, RvRequest *q,
                    uint32_t replica, uint32_t preserve)
{
    pn_zero(q,sizeof(*q)); q->version=1; q->bytes=sizeof(*q);
    q->args[0]=s->epoch; q->args[2]=o->kind; q->args[3]=o->unit;
    q->args[4]=o->slot; q->args[5]=replica; q->args[10]=preserve;
}
static int32_t rpc(PsStore *s, uint32_t op, RvRequest *q, RvReply *r)
{
    int32_t v=pn_call(s->port,RV_STORAGE,op,q,r);
    if (v==RV_UNCERTAIN) return fence(s);
    if (v==RV_VERIFY || (v==RV_OK && (!r->epoch || r->epoch!=s->epoch))) {
        if (op==2 || (op>=3 && op!=4)) return fence(s);
        return RV_STALE;
    }
    return v;
}
static int32_t caps(PsStore *s)
{
    RvRequest q; RvReply r; int32_t v;
    pn_zero(&q,sizeof(q)); q.version=1; q.bytes=sizeof(q);
    v=pn_call(s->port,RV_STORAGE,1,&q,&r);
    if (v!=RV_OK) return v;
    if (!r.epoch || (s->epoch && s->epoch!=r.epoch)) return RV_STALE;
    s->epoch=r.epoch; s->caps=r.capabilities;
    return RV_OK;
}
static int32_t begin(PsStore *s, const PsObject *o, int writing)
{
    int32_t v;
    if (!s || !s->port || !s->work || (o && o->kind==PS_ENGINE && !s->verify) || !object_ok(o) ||
        s->capacity<limit(o)) return RV_ARGUMENT;
    if (s->busy) return RV_BUSY;
    if (writing && s->uncertain) return RV_UNCERTAIN;
    s->busy=1;
    v=caps(s);
    if (v!=RV_OK) { s->busy=0; return v; }
    if (!(s->caps&PS_READ_IROM)) { s->busy=0; return RV_UNSUPPORTED; }
    if (writing && (s->caps&(PS_WRITE|PS_RENAME))!=(PS_WRITE|PS_RENAME)) {
        s->busy=0; return RV_UNSUPPORTED;
    }
    if (!s->uncertain) s->stage=PS_SCANNING;
    return RV_OK;
}
static int32_t finish(PsStore *s, int32_t v)
{
    s->busy=0;
    if (s->uncertain) s->stage=PS_COMMIT_UNCERTAIN;
    return v;
}

void ps_init(PsStore *s, PnPort *p, uint8_t *work, uint32_t n,
             PsVerify verify, void *context)
{
    pn_zero(s,sizeof(*s)); s->port=p; s->work=work; s->capacity=n;
    s->verify=verify; s->verify_context=context;
}
static int32_t open_read(PsStore *s, const PsObject *o, uint32_t replica,
                         uint32_t *token)
{
    RvRequest q; RvReply r; int32_t v;
    request(s,o,&q,replica,0); v=rpc(s,2,&q,&r);
    if (v==RV_OK) {
        if (!r.token) return fence(s);
        *token=r.token;
    }
    return v;
}
static int32_t close_once(PsStore *s, uint32_t token)
{
    RvRequest q; RvReply r;
    pn_zero(&q,sizeof(q)); q.version=1; q.bytes=sizeof(q);
    q.args[0]=s->epoch; q.args[1]=token;
    /* CLOSE invalidates the token even on failure. Never retry it. */
    if (rpc(s,6,&q,&r)!=RV_OK) return fence(s);
    return RV_OK;
}
static int32_t transfer(PsStore *s, uint32_t op, uint32_t token, void *data,
                        uint32_t n, uint32_t *actual)
{
    RvRequest q; RvReply r; int32_t v;
    pn_zero(&q,sizeof(q)); q.version=1; q.bytes=sizeof(q);
    q.args[0]=s->epoch; q.args[1]=token;
    q.args[6]=pn_address(s->port,data,n); q.args[7]=n;
    if (!q.args[6]) return RV_ARGUMENT;
    v=rpc(s,op,&q,&r);
    if (v!=RV_OK && !(op==4 && v==RV_EOF)) return v;
    if (r.actual>n) return op==5 ? fence(s) : RV_IO;
    if (op==5 && !r.actual) return RV_IO;
    if (r.epoch!=s->epoch) return op==5 ? fence(s) : RV_STALE;
    *actual=r.actual;
    return v;
}
static int32_t read_file(PsStore *s, const PsObject *o, uint32_t replica,
                         uint32_t *bytes, uint8_t *observed)
{
    uint32_t token=0,n=0,got=0,max=limit(o);
    int32_t v=open_read(s,o,replica,&token), c;
    if (observed) *observed=0;
    if (v!=RV_OK) return v;
    if (observed) *observed=1;
    for (;;) {
        uint32_t want=n<max ? max-n : 1;
        void *dest=n<max ? s->work+n : s->chunk;
        v=transfer(s,4,token,dest,want,&got);
        if (v!=RV_OK && v!=RV_EOF) break;
        if (n==max && got) { v=RV_VERIFY; break; }
        n+=got;
        if (!got || v==RV_EOF) { v=RV_OK; break; }
    }
    c=close_once(s,token);
    if (c!=RV_OK) return c;
    if (v==RV_OK) *bytes=n;
    return v;
}
static int32_t inspect(PsStore *s, const PsObject *o, const uint8_t *p,
                       uint32_t n, PsInfo *i)
{
    int32_t v;
    if (!n || n>limit(o)) return RV_VERIFY;
    pn_zero(i,sizeof(*i));
    v=s->verify(s->verify_context,o,p,n,i);
    if (v==RV_OK && i->bytes!=n) return RV_VERIFY;
    return v;
}
static int info_equal(const PsInfo *a, const PsInfo *b)
{
    return a->generation==b->generation && a->bytes==b->bytes &&
           a->crc32==b->crc32;
}
static int32_t exact_file(PsStore *s, const PsObject *o, unsigned replica,
                          const uint8_t *raw, uint32_t n)
{
    uint32_t token=0,pos=0,got=0,want;int32_t v=open_read(s,o,replica,&token),c;
    if (v!=RV_OK) return v;
    while (pos<n) {
        want=n-pos;if(want>sizeof(s->chunk)) want=sizeof(s->chunk);
        v=transfer(s,4,token,s->chunk,want,&got);
        if ((v!=RV_OK && v!=RV_EOF) || !got) {if(v==RV_OK || v==RV_EOF)v=RV_VERIFY;break;}
        if (!pn_equal(s->chunk,raw+pos,got)) {v=RV_VERIFY;break;}
        pos+=got;v=RV_OK;
    }
    if(v==RV_OK) {
        v=transfer(s,4,token,s->chunk,1,&got);
        if((v==RV_OK || v==RV_EOF) && !got) v=RV_OK;
        else if(v==RV_OK || v==RV_EOF) v=RV_VERIFY;
    }
    c=close_once(s,token);return c!=RV_OK?c:v;
}
static int32_t scan(PsStore *s, const PsObject *o, PsCandidate c[2], unsigned *best)
{
    unsigned j; int32_t v; uint32_t n;
    *best=2;
    for (j=0;j<2;j++) {
        pn_zero(&c[j],sizeof(c[j])); c[j].replica=(uint8_t)(PS_A+j);
        v=read_file(s,o,c[j].replica,&n,&c[j].observed);
        if (v==RV_UNAVAILABLE && !c[j].observed) continue;
        if (v==RV_OK) v=inspect(s,o,s->work,n,&c[j].info);
        if (v==RV_VERIFY || v==RV_RANGE) continue;
        if (v!=RV_OK) return v;
        c[j].valid=1;
        if (*best==2 || c[j].info.generation>c[*best].info.generation) *best=j;
    }
    if (c[0].valid && c[1].valid && c[0].info.generation==c[1].info.generation) {
        if (!info_equal(&c[0].info,&c[1].info)) return RV_CONFLICT;
        v=exact_file(s,o,PS_A,s->work,c[1].info.bytes);
        if(v!=RV_OK) return v==RV_VERIFY?RV_CONFLICT:v;
    }
    return RV_OK;
}
static int32_t compare_file(PsStore *s, const PsObject *o, uint32_t replica,
                            const uint8_t *raw, uint32_t bytes, const PsInfo *want)
{
    uint32_t n=0; PsInfo got; int32_t v=read_file(s,o,replica,&n,0);
    if (v!=RV_OK) return v;
    if (n!=bytes || !pn_equal(s->work,raw,n)) return RV_VERIFY;
    v=inspect(s,o,s->work,n,&got);
    return v==RV_OK && !info_equal(&got,want) ? RV_VERIFY : v;
}
int32_t ps_load(PsStore *s, const PsObject *o, uint8_t *out, uint32_t cap,
                uint32_t *bytes, PsCandidate *chosen)
{
    PsCandidate c[2]; unsigned best; uint32_t n=0; PsInfo i;
    int32_t v;
    if (!s || !o || o->kind!=PS_ENGINE || !s->verify || !out || !bytes || !chosen)
        return RV_ARGUMENT;
    *bytes=0; pn_zero(chosen,sizeof(*chosen));
    v=begin(s,o,0); if (v!=RV_OK) return v;
    v=scan(s,o,c,&best);
    if (v==RV_OK && best==2) v=RV_UNAVAILABLE;
    if (v==RV_OK) {
        v=read_file(s,o,c[best].replica,&n,0);
        if (v==RV_OK) v=inspect(s,o,s->work,n,&i);
        if (v==RV_OK && !info_equal(&i,&c[best].info)) v=RV_STALE;
        if (v==RV_OK && n>cap) v=RV_RANGE;
        if (v==RV_OK) { pn_copy(out,s->work,n); *bytes=n; *chosen=c[best]; }
    }
    return finish(s,v);
}
static int overlaps(const uint8_t *a, uint32_t an, const uint8_t *b, uint32_t bn)
{
    uintptr_t x=(uintptr_t)a,y=(uintptr_t)b;
    return x<=y ? y-x<an : x-y<bn;
}
static int32_t remove_owned(PsStore *s, const PsObject *o, uint32_t replica,
                             uint32_t preserve)
{
    RvRequest q; RvReply r;
    if (!(s->caps&PS_DELETE)) return RV_UNSUPPORTED;
    request(s,o,&q,replica,preserve);
    return rpc(s,8,&q,&r);
}
static int32_t write_all(PsStore *s, uint32_t token, const uint8_t *p, uint32_t n)
{
    uint32_t pos=0,got; int32_t v;
    while (pos<n) {
        v=transfer(s,5,token,(void *)(p+pos),n-pos,&got);
        if (v!=RV_OK) return v;
        pos+=got;
    }
    return RV_OK;
}
static int32_t write_temp(PsStore *s, const PsObject *o, const uint8_t *raw,
                           uint32_t n, uint32_t preserve, int from_card)
{
    RvRequest q; RvReply r;
    uint32_t source=0,target=0,pos=0,got=0,want;
    int32_t v=RV_OK, ct=RV_OK, cs=RV_OK;
    /* Old TEMP is never a candidate. Only this fixed object's TEMP is removed. */
    if (s->caps&PS_DELETE) {
        v=remove_owned(s,o,PS_TEMP,preserve);
        if (v!=RV_OK && v!=RV_UNAVAILABLE) return v;
    }
    if (from_card) {
        v=open_read(s,o,PS_CARD,&source);
        if (v!=RV_OK) return v;
    }
    request(s,o,&q,PS_TEMP,preserve); q.args[8]=n;
    v=rpc(s,3,&q,&r);
    if (v==RV_OK) {
        target=r.token;
        if (!target) v=fence(s);
    }
    if (v==RV_OK) {
        s->stage=PS_WRITING;
        while (pos<n) {
            want=n-pos; if (want>sizeof(s->chunk)) want=sizeof(s->chunk);
            if (from_card) {
                v=transfer(s,4,source,s->chunk,want,&got);
                if ((v!=RV_OK && v!=RV_EOF) || !got) {
                    if (v==RV_OK || v==RV_EOF) v=RV_VERIFY;
                    break;
                }
                if (!pn_equal(s->chunk,raw+pos,got)) { v=RV_VERIFY; break; }
            } else { got=want; pn_copy(s->chunk,raw+pos,got); }
            v=write_all(s,target,s->chunk,got);
            if (v!=RV_OK) break;
            pos+=got;
        }
        if (v==RV_OK && from_card) {
            v=transfer(s,4,source,s->chunk,1,&got);
            if ((v==RV_OK || v==RV_EOF) && !got) v=RV_OK;
            else if (v==RV_OK || v==RV_EOF) v=RV_VERIFY;
        }
    }
    if (target) ct=close_once(s,target);
    if (source) cs=close_once(s,source);
    if (ct!=RV_OK || cs!=RV_OK) return RV_UNCERTAIN;
    return v;
}
static int32_t commit(PsStore *s, const PsObject *o, const uint8_t *raw,
                       uint32_t n, const PsInfo *info, PsCandidate c[2],
                       unsigned best, int from_card, uint8_t *saved)
{
    uint32_t preserve=best==2 ? 0 : c[best].replica;
    unsigned dest=best==2 ? (c[0].observed && !c[1].observed ? 1 : 0) : 1-best;
    RvRequest q; RvReply r;
    int32_t v;
    if (best==2 && c[dest].observed) return RV_VERIFY;
    v=write_temp(s,o,raw,n,preserve,from_card);
    if (v!=RV_OK) return v;
    s->stage=PS_TEMP_CHECK;
    v=compare_file(s,o,PS_TEMP,raw,n,info);
    if (v!=RV_OK) return v;
    if (c[dest].observed) {
        /* Never delete ANY formal replica without another verified survivor. */
        if (!preserve) return RV_VERIFY;
        v=remove_owned(s,o,c[dest].replica,preserve);
        if (v!=RV_OK) return v;
    }
    request(s,o,&q,PS_TEMP,preserve); q.args[9]=c[dest].replica;
    s->stage=PS_RENAMING;
    v=rpc(s,7,&q,&r);
    if (v!=RV_OK) return fence(s);
    s->stage=PS_FINAL_CHECK;
    v=compare_file(s,o,c[dest].replica,raw,n,info);
    if (v!=RV_OK) return fence(s);
    *saved=c[dest].replica; s->stage=PS_SAVED;
    return RV_OK;
}
static int32_t acknowledge(PsStore *s, const PsObject *o, const uint8_t *raw,
                            uint32_t n, const PsInfo *info, uint8_t saved)
{
    RvRequest q; RvReply r; int32_t v;
    if (!(s->caps&PS_MARK)) return RV_UNSUPPORTED;
    /* Recheck the formal candidate and current DAT even on equal-generation
     * reinstall. The resident additionally binds all 16 SD ID bytes. */
    v=compare_file(s,o,saved,raw,n,info);
    if (v==RV_OK) v=compare_file(s,o,PS_CARD,raw,n,info);
    if (v!=RV_OK) return v;
    request(s,o,&q,PS_CARD,saved); q.args[9]=PS_DELIVERED;
    s->stage=PS_ACKING;
    v=rpc(s,9,&q,&r);
    if (v!=RV_OK) return fence(s);
    v=compare_file(s,o,PS_DELIVERED,raw,n,info);
    if (v!=RV_OK) return fence(s);
    s->stage=PS_DONE;
    return RV_OK;
}
int32_t ps_install(PsStore *s, const uint8_t *raw, uint32_t n, PsInstallResult *out)
{
    const PsObject o={PS_ENGINE,0,0};
    PsInfo info; PsCandidate c[2]; unsigned best; uint8_t saved=0;
    int32_t v;
    if (!out) return RV_ARGUMENT;
    pn_zero(out,sizeof(*out)); out->save_status=RV_ARGUMENT;
    out->delivery_status=RV_UNSUPPORTED;
    if (!s || !raw || !n || n>PS_MAX_ENGINE ||
        overlaps(raw,n,s->work,s->capacity)) return RV_ARGUMENT;
    if (s->uncertain) { out->save_status=RV_UNCERTAIN; return RV_UNCERTAIN; }
    /* Equal-generation IROM can be acknowledged without write-temp capability. */
    v=begin(s,&o,0);
    if (v!=RV_OK) { out->save_status=v; return v; }
    if (s->uncertain) v=RV_UNCERTAIN;
    else if (!(s->caps&PS_READ_CARD)) v=RV_UNSUPPORTED;
    else v=inspect(s,&o,raw,n,&info);
    if (v==RV_OK) v=scan(s,&o,c,&best);
    if (v==RV_OK && best!=2 && info.generation<c[best].info.generation)
        v=RV_CONFLICT;
    if (v==RV_OK && best!=2 && info.generation==c[best].info.generation) {
        if (!info_equal(&info,&c[best].info)) v=RV_CONFLICT;
        else {
            v=compare_file(s,&o,c[best].replica,raw,n,&info);
            if(v==RV_VERIFY)v=RV_CONFLICT;
            if(v==RV_OK){saved=c[best].replica;s->stage=PS_SAVED;}
        }
    } else if (v==RV_OK) {
        if ((s->caps&(PS_WRITE|PS_RENAME))!=(PS_WRITE|PS_RENAME)) v=RV_UNSUPPORTED;
        else v=commit(s,&o,raw,n,&info,c,best,1,&saved);
    }
    out->save_status=v;
    if (v==RV_OK) {
        out->installed=1; out->replica=saved;
        v=acknowledge(s,&o,raw,n,&info,saved);
        out->delivery_status=v; out->delivered=(uint8_t)(v==RV_OK);
    }
    return finish(s,v);
}

int32_t ps_fixed_begin(PsStore *s,const PsObject *o,int writing)
{ return begin(s,o,writing); }
int32_t ps_fixed_end(PsStore *s,int32_t v) { return finish(s,v); }
int32_t ps_fixed_open(PsStore *s,const PsObject *o,unsigned replica,int writing,
                       uint32_t preserve,uint32_t bytes,uint32_t *token)
{
    RvRequest q;RvReply r;int32_t v;
    if(!object_ok(o) || !token || replica<PS_CARD || replica>PS_DELIVERED) return RV_ARGUMENT;
    if(!writing) return open_read(s,o,replica,token);
    if(s->uncertain) return RV_UNCERTAIN;
    if(replica!=PS_TEMP || !bytes || bytes>limit(o)) return RV_ARGUMENT;
    request(s,o,&q,replica,preserve);q.args[8]=bytes;v=rpc(s,3,&q,&r);
    if(v==RV_OK) {if(!r.token)return fence(s);*token=r.token;}return v;
}
int32_t ps_fixed_transfer(PsStore *s,unsigned op,uint32_t token,void *p,
                           uint32_t n,uint32_t *actual)
{ return transfer(s,op,token,p,n,actual); }
int32_t ps_fixed_close(PsStore *s,uint32_t token) { return close_once(s,token); }
int32_t ps_fixed_remove(PsStore *s,const PsObject *o,unsigned replica,uint32_t preserve)
{
    if(s->uncertain) return RV_UNCERTAIN;
    if(replica!=PS_TEMP && (!preserve || replica==preserve)) return RV_ARGUMENT;
    return remove_owned(s,o,replica,preserve);
}
int32_t ps_fixed_rename(PsStore *s,const PsObject *o,unsigned target,uint32_t preserve)
{
    RvRequest q;RvReply r;int32_t v;
    if(s->uncertain) return RV_UNCERTAIN;
    if((target!=PS_A && target!=PS_B) || target==preserve) return RV_ARGUMENT;
    request(s,o,&q,PS_TEMP,preserve);q.args[9]=target;v=rpc(s,7,&q,&r);
    return v==RV_OK?RV_OK:fence(s);
}

