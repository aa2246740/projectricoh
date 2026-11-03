#include "gxts.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static int failures;
static void check(int ok,const char *s) { if(!ok) { fprintf(stderr,"GXTS FAIL %s\n",s); ++failures; } }
static void p16(uint8_t *p,unsigned v) { p[0]=(uint8_t)(v>>8); p[1]=(uint8_t)v; }
static void p32(uint8_t *p,uint32_t v) { p[0]=(uint8_t)(v>>24); p[1]=(uint8_t)(v>>16); p[2]=(uint8_t)(v>>8); p[3]=(uint8_t)v; }
static void seal(uint8_t *b) { memset(b+16,0,4); p32(b+16,gxr2_crc32(b,GXTS_BYTES)); }
typedef struct {
    uint8_t data[3][257]; uint32_t length[3],position;
    unsigned exists[3],open,which,writing,calls,fail_at,failed,violations,chunk,zero_write,oversized;
} Mock;
static int op(Mock *m) { ++m->calls; if(m->calls==m->fail_at) { m->failed=1; return -1; } return 0; }
static int open_cb(void *c,unsigned module,unsigned slot,unsigned which,int write,uint32_t *handle)
{
    Mock *m=c; if(op(m)) return -1;
    if(module || slot || which>2 || m->open || (write && which!=2)) { ++m->violations; return -1; }
    if(!write && !m->exists[which]) return 1;
    m->open=1; m->which=which; m->writing=(unsigned)write; m->position=0; *handle=123;
    if(write) { m->exists[which]=1; m->length[which]=0; } return 0;
}
static int read_cb(void *c,uint32_t handle,uint8_t *b,uint32_t request,uint32_t *actual)
{
    Mock *m=c; uint32_t n; if(op(m)) return -1;
    if(handle!=123 || !m->open || m->writing || request>256) { ++m->violations; return -1; }
    n=m->length[m->which]-m->position; if(n>request) n=request; if(n>m->chunk) n=m->chunk;
    memcpy(b,m->data[m->which]+m->position,n); m->position+=n; *actual=n; return 0;
}
static int write_cb(void *c,uint32_t handle,const uint8_t *b,uint32_t request,uint32_t *actual)
{
    Mock *m=c; uint32_t n=request; if(op(m)) return -1;
    if(handle!=123 || !m->open || !m->writing) { ++m->violations; return -1; }
    if(m->zero_write) { *actual=0; return 0; }
    if(m->oversized) { *actual=request+1; return 0; }
    if(n>m->chunk) n=m->chunk;
    memcpy(m->data[2]+m->position,b,n); m->position+=n; m->length[2]=m->position; *actual=n; return 0;
}
static int close_cb(void *c,uint32_t handle)
{
    Mock *m=c; int rc=op(m);
    if(handle!=123 || !m->open) { ++m->violations; return -1; }
    m->open=0; return rc;
}
static int remove_cb(void *c,unsigned module,unsigned slot,unsigned which)
{
    Mock *m=c; if(op(m)) return -1;
    if(module || slot || which==0 || which>2 || m->open) { ++m->violations; return -1; }
    if(!m->exists[which]) return 1;
    m->exists[which]=0; m->length[which]=0; return 0;
}
static int rename_cb(void *c,unsigned module,unsigned slot,unsigned target)
{
    Mock *m=c; if(op(m)) return -1;
    if(module || slot || target>1 || m->open || !m->exists[2] || m->exists[target]) { ++m->violations; return -1; }
    memcpy(m->data[target],m->data[2],m->length[2]); m->length[target]=m->length[2];
    m->exists[target]=1; m->exists[2]=0; return 0;
}
int test_gxts(const Gxr2View *view)
{
    GxtsBinding b,other; GxtsState state,decoded,sentinel;
    GxtsSelection selected,selection_sentinel; GxtsIO io;
    uint8_t a[GXTS_BYTES],bb[GXTS_BYTES],changed[GXTS_BYTES],*small;
    Mock base,m; unsigned i,k,normal_calls; GxtsStatus status;
    check(gxts_bind(view,0,1,&b)==GXTS_OK,"binding from full semantic view");
    check(gxts_bind(view,1,1,&other)==GXTS_OK,"28mm binding");
    gxts_defaults(&b,&state); check(state.generation==0 && state.values[0]==0,"metadata defaults");
    state.generation=1; state.values[0]=-5; state.values[1]=5;
    check(gxts_encode(&b,&state,a)==GXTS_OK,"encode signed values");
    check(gxts_decode(a,sizeof(a),&b,&decoded)==GXTS_OK && decoded.values[0]==-5 && decoded.values[1]==5,"decode literal values");
    check(gxts_decode(a,sizeof(a),&other,&decoded)==GXTS_IDENTITY,"foreign module rejected");
    memset(&sentinel,0xa5,sizeof(sentinel)); memset(&selection_sentinel,0xa5,sizeof(selection_sentinel));
    for(i=0;i<GXTS_BYTES;++i) {
        small=malloc(i?i:1); if(!small) return 1; memcpy(small,a,i); decoded=sentinel;
        check(gxts_decode(small,i,&b,&decoded)!=GXTS_OK,"all exact state truncations");
        check(!memcmp(&decoded,&sentinel,sizeof(decoded)),"state output unchanged on truncation"); free(small);
        memcpy(changed,a,sizeof(a)); changed[i]^=128;
        check(gxts_decode(changed,sizeof(changed),&b,&decoded)!=GXTS_OK,"all state single-byte corruptions");
    }
    for(i=0;i<160;++i) {
        memcpy(changed,a,sizeof(a)); changed[20+i]^=1; seal(changed);
        check(gxts_decode(changed,sizeof(changed),&b,&decoded)==GXTS_IDENTITY,"every identity byte is bound after CRC repair");
    }
    memcpy(changed,a,sizeof(a)); p32(changed+12,0); seal(changed);
    check(gxts_decode(changed,sizeof(changed),&b,&decoded)==GXTS_GENERATION,"zero generation");
    memcpy(changed,a,sizeof(a)); p32(changed+196,UINT32_C(0x80000000)); seal(changed);
    check(gxts_decode(changed,sizeof(changed),&b,&decoded)==GXTS_RANGE,"INT32_MIN out of range");
    for(i=0;i<6;++i) {
        memcpy(changed,a,sizeof(a)); p32(changed+192+8*i,99); seal(changed);
        check(gxts_decode(changed,sizeof(changed),&b,&decoded)==GXTS_VERSION,"unknown parameter ID");
    }
    memcpy(changed,a,sizeof(a)); p32(changed+200,1); seal(changed);
    check(gxts_decode(changed,sizeof(changed),&b,&decoded)==GXTS_VERSION,"duplicate parameter ID");
    memcpy(changed,a,sizeof(a)); p16(changed+180,8); seal(changed);
    check(gxts_decode(changed,sizeof(changed),&b,&decoded)==GXTS_VERSION,"count mismatch");
    memcpy(changed,a,sizeof(a)); p32(changed+188,1); seal(changed);
    check(gxts_decode(changed,sizeof(changed),&b,&decoded)==GXTS_VERSION,"flags rejected");
    state.generation=2; state.values[0]=2; check(gxts_encode(&b,&state,bb)==GXTS_OK,"second generation");
    check(gxts_select(a,sizeof(a),bb,sizeof(bb),&b,&selected)==GXTS_OK && selected.selected==1 && selected.state.generation==2,"newer B wins");
    bb[239]^=1;
    check(gxts_select(a,sizeof(a),bb,sizeof(bb),&b,&selected)==GXTS_OK && selected.selected==0 && selected.invalid_mask==2,"bad higher generation cannot hide A");
    state.generation=1; check(gxts_encode(&b,&state,bb)==GXTS_OK,"equal generation different content"); selected=selection_sentinel;
    check(gxts_select(a,sizeof(a),bb,sizeof(bb),&b,&selected)==GXTS_CONFLICT && !memcmp(&selected,&selection_sentinel,sizeof(selected)),"A/B conflict unchanged output");
    check(gxts_select(a,sizeof(a),a,sizeof(a),&b,&selected)==GXTS_OK && selected.selected==0,"identical equal generation");
    check(gxts_select(NULL,0,NULL,0,&b,&selected)==GXTS_MISSING,"missing copies use defaults");
    memset(&base,0,sizeof(base)); base.chunk=37; base.exists[0]=1; base.length[0]=GXTS_BYTES; memcpy(base.data[0],a,sizeof(a));
    io.context=&m; io.open=open_cb; io.read=read_cb; io.write=write_cb; io.close=close_cb; io.remove=remove_cb; io.rename_temp=rename_cb;
    m=base; check(gxts_save(&io,&b,state.values,&selected)==GXTS_OK && selected.selected==1 && selected.state.generation==2,"transaction short read/write and nonselected B");
    check(m.exists[0] && !memcmp(m.data[0],a,sizeof(a)) && !m.open && !m.violations,"old A retained"); normal_calls=m.calls;
    check(gxts_load(&io,&b,&selected)==GXTS_OK && selected.selected==1 && selected.state.values[0]==2,"saved B read after restart model");
    for(k=1;k<=normal_calls;++k) {
        m=base; m.fail_at=k; selected=selection_sentinel; status=gxts_save(&io,&b,state.values,&selected);
        check(m.failed && status!=GXTS_OK,"each callback failure rejected");
        check(!m.open && !m.violations && m.exists[0] && !memcmp(m.data[0],a,sizeof(a)),"every failed save retains old A, closes once");
        check(!memcmp(&selected,&selection_sentinel,sizeof(selected)),"failed save output unchanged");
    }
    m=base; m.zero_write=1; check(gxts_save(&io,&b,state.values,&selected)==GXTS_UNCERTAIN && !m.open,"zero write stops");
    m=base; m.oversized=1; check(gxts_save(&io,&b,state.values,&selected)==GXTS_UNCERTAIN && !m.open,"oversized actual stops");
    state.generation=UINT32_MAX; check(gxts_encode(&b,&state,bb)==GXTS_OK,"max generation codec");
    m=base; memcpy(m.data[0],bb,sizeof(bb));
    check(gxts_save(&io,&b,state.values,&selected)==GXTS_GENERATION && !m.exists[2],"no generation wrap and no temp write");
    m=base; memcpy(m.data[1],a,sizeof(a)); m.length[1]=GXTS_BYTES; m.exists[1]=1;
    m.data[1][239]^=1; seal(m.data[1]);
    check(gxts_save(&io,&b,state.values,&selected)==GXTS_CONFLICT && !m.exists[2],"conflict prevents writes");
    memset(&m,0,sizeof(m)); m.chunk=37;
    check(gxts_save(&io,&b,state.values,&selected)==GXTS_OK && selected.selected==0 && selected.state.generation==1,"first save to A");
    printf("gxts truncations=240 corruptions=240 identity_mutations=160 io_failure_points=%u failures=%d\n",normal_calls,failures);
    return failures;
}
