#include "panel_gxts.h"
#include <limits.h>

static PsObject object(PnGxts *a)
{ PsObject o={PS_TWEAK,(uint8_t)(a->binding.module+1),(uint8_t)(a->binding.slot-1)};return o; }
static int key(PnGxts *a,unsigned module,unsigned slot,unsigned copy)
{ return module==a->binding.module && slot+1==a->binding.slot && copy<=GXTS_TEMP; }
static int result(PnGxts *a,int32_t v)
{
    if(v==RV_OK) return 0;
    if(v==RV_UNCERTAIN) a->store->uncertain=1;
    return v==RV_UNAVAILABLE?1:-1;
}
static int io_open(void *ctx,unsigned module,unsigned slot,unsigned copy,int write,uint32_t *token)
{
    PnGxts *a=ctx;PsObject o=object(a);int32_t v;
    if(!key(a,module,slot,copy) || a->token || (write && copy!=GXTS_TEMP)) return -1;
    if(copy==GXTS_A && !write) {a->valid_mask=0;a->preserve=0;}
    a->active_copy=(uint8_t)copy;a->captured=0;a->eof=0;a->read_failed=0;
    v=ps_fixed_open(a->store,&o,copy+PS_A,write,a->preserve,write?GXTS_BYTES:0,token);
    if(v==RV_OK) a->token=*token;
    return result(a,v);
}
static int io_read(void *ctx,uint32_t token,uint8_t *out,uint32_t n,uint32_t *actual)
{
    PnGxts *a=ctx;uint32_t got=0;int32_t v;
    if(token!=a->token || !n || n>256) return -1;
    /* Upstream probes up to 257 B. Resident's object cap is 256 B. Clamp
     * requests so a legitimate short 240 B record can still reach EOF. */
    if(a->captured>=PS_MAX_TWEAK) {a->read_failed=1;return -1;}
    if(n>PS_MAX_TWEAK-a->captured)n=PS_MAX_TWEAK-a->captured;
    v=ps_fixed_transfer(a->store,4,token,a->store->chunk,n,&got);
    if(v!=RV_OK && v!=RV_EOF) {a->read_failed=1;return result(a,v);}
    if(a->captured>sizeof(a->capture)-got) {a->read_failed=1;return -1;}
    pn_copy(out,a->store->chunk,got);pn_copy(a->capture+a->captured,a->store->chunk,got);
    a->captured+=got;if(!got)a->eof=1;*actual=got;return 0;
}
static int io_write(void *ctx,uint32_t token,const uint8_t *in,uint32_t n,uint32_t *actual)
{
    PnGxts *a=ctx;int32_t v;
    if(token!=a->token || a->active_copy!=GXTS_TEMP || !n || n>GXTS_BYTES) return -1;
    pn_copy(a->store->chunk,in,n);
    v=ps_fixed_transfer(a->store,5,token,a->store->chunk,n,actual);return result(a,v);
}
static int io_close(void *ctx,uint32_t token)
{
    PnGxts *a=ctx;GxtsState state;int32_t v;unsigned copy=a->active_copy;
    if(token!=a->token) return -1;
    a->token=0;v=ps_fixed_close(a->store,token);
    if(v==RV_OK && copy<=GXTS_B && a->eof && !a->read_failed &&
       gxts_decode(a->capture,a->captured,&a->binding,&state)==GXTS_OK) {
        a->valid_mask|=(uint8_t)(1u<<copy);a->generation[copy]=state.generation;
        if(a->valid_mask==1 || (a->valid_mask==3 && a->generation[0]>=a->generation[1]))a->preserve=PS_A;
        else a->preserve=PS_B;
    }
    return result(a,v);
}
static int io_remove(void *ctx,unsigned module,unsigned slot,unsigned copy)
{
    PnGxts *a=ctx;PsObject o=object(a);
    if(!key(a,module,slot,copy) || a->token) return -1;
    return result(a,ps_fixed_remove(a->store,&o,copy+PS_A,a->preserve));
}
static int io_rename(void *ctx,unsigned module,unsigned slot,unsigned target)
{
    PnGxts *a=ctx;PsObject o=object(a);
    if(!key(a,module,slot,target) || target>GXTS_B || a->token) return -1;
    return result(a,ps_fixed_rename(a->store,&o,target+PS_A,a->preserve));
}
static int32_t mapped(PnGxts *a,GxtsStatus v)
{
    if(v==GXTS_UNCERTAIN || a->store->uncertain) {
        a->store->uncertain=1;a->store->stage=PS_COMMIT_UNCERTAIN;return RV_UNCERTAIN;
    }
    switch(v) {
    case GXTS_OK:return RV_OK;
    case GXTS_MISSING:return RV_UNAVAILABLE;
    case GXTS_IO:return RV_IO;
    case GXTS_CONFLICT:return RV_CONFLICT;
    case GXTS_GENERATION:case GXTS_RANGE:return RV_RANGE;
    case GXTS_ARGUMENT:return RV_ARGUMENT;
    default:return RV_VERIFY;
    }
}
int32_t pn_gxts_attach(PnGxts *a,PsStore *s,const GxtsBinding *b,const EngRecipeRef *r,const uint8_t index[6])
{
    unsigned i,mask=0;
    if(!a || !s || !b || !r || !index || r->unit>2 || r->slot<1 || r->slot>16 ||
       b->module!=r->unit || b->slot!=r->slot || !pn_equal(r->identity,b->identity+44,49)) return RV_ARGUMENT;
    for(i=0;i<6;i++) {
        unsigned x=index[i];
        if(x>=ENG_PARAMS || (mask&(1u<<x)) || b->lo[i]<INT8_MIN || b->hi[i]>INT8_MAX ||
           b->lo[i]>b->def[i] || b->def[i]>b->hi[i]) return RV_RANGE;
        mask|=1u<<x;
    }
    pn_zero(a,sizeof(*a));a->store=s;a->binding=*b;a->recipe=*r;pn_copy(a->param_index,index,6);
    a->io=(GxtsIO){a,io_open,io_read,io_write,io_close,io_remove,io_rename};return RV_OK;
}
int32_t pn_gxts_load(PnGxts *a,EngTweak *out)
{
    PsObject o;GxtsSelection selected;GxtsStatus status;EngTweak t;unsigned i;int32_t v;
    if(!a || !out || !a->store) return RV_ARGUMENT;
    o=object(a);v=ps_fixed_begin(a->store,&o,0);if(v!=RV_OK)return v;
    status=gxts_load(&a->io,&a->binding,&selected);
    if(status==GXTS_MISSING) {
        pn_zero(&selected,sizeof(selected));gxts_defaults(&a->binding,&selected.state);a->used_defaults=1;
    } else a->used_defaults=0;
    if(status==GXTS_OK || status==GXTS_MISSING) {
        pn_zero(&t,sizeof(t));for(i=0;i<6;i++)t.v[a->param_index[i]]=(int8_t)selected.state.values[i];
        *out=t;a->selection=selected;a->loaded=1;v=a->store->uncertain?RV_UNCERTAIN:RV_OK;
    } else v=mapped(a,status);
    return ps_fixed_end(a->store,v);
}
int32_t pn_gxts_save(void *ctx,const EngRecipeRef *r,const EngTweak *t)
{
    PnGxts *a=ctx;PsObject o;GxtsStatus status;GxtsSelection selected;
    int32_t values[6],v;unsigned i,mask=0;
    if(!a || !a->store || !r || !t) return RV_ARGUMENT;
    if(a->store->uncertain) return RV_UNCERTAIN;
    if(r->unit!=a->recipe.unit || r->slot!=a->recipe.slot || !pn_equal(r->identity,a->recipe.identity,49)) return RV_STALE;
    if(a->loaded && a->selection.io_error_mask) return RV_IO;
    for(i=0;i<6;i++) {values[i]=t->v[a->param_index[i]];mask|=1u<<a->param_index[i];}
    for(i=0;i<ENG_PARAMS;i++)if(!(mask&(1u<<i)) && t->v[i])return RV_RANGE;
    o=object(a);v=ps_fixed_begin(a->store,&o,1);if(v!=RV_OK)return v;
    if(!(a->store->caps&PS_DELETE))return ps_fixed_end(a->store,RV_UNSUPPORTED);
    status=gxts_save(&a->io,&a->binding,values,&selected);v=mapped(a,status);
    if(v==RV_OK){a->selection=selected;a->loaded=1;a->used_defaults=0;}return ps_fixed_end(a->store,v);
}
