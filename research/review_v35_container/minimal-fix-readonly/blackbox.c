#include "blackbox.h"
#include "src/firmware/card_container_v2/internal.h"
static RvPrivateContext *ctx;
static uint8_t *log_bytes;
static uint32_t get32(const uint8_t *p){return (uint32_t)p[0]<<24|(uint32_t)p[1]<<16|(uint32_t)p[2]<<8|p[3];}
static void p16(uint8_t *p,unsigned v){p[0]=v>>8;p[1]=v;}
static void p32(uint8_t *p,uint32_t v){p[0]=v>>24;p[1]=v>>16;p[2]=v>>8;p[3]=v;}
static uint32_t crc(const uint8_t *p,unsigned n){return gxr2_crc32(p,n);}
static int card(uint32_t id[4]){return !rv_native_sd_id(id)&&(id[0]|id[1]|id[2]|id[3]);}
int ig_control_off(void)
{
    uint32_t before[4],after[4];uint8_t raw[16],extra;unsigned at=0;int32_t fd,n,closed;int ok=1;
    if(!card(before))return 0;
    fd=rv_native_open("/ATA1/GXRCE.CTL",0);if(fd<0)return 0;
    while(at<16){n=rv_native_read(fd,raw+at,16-at);if(n<=0||(unsigned)n>16-at){ok=0;break;}at+=(unsigned)n;}
    n=rv_native_read(fd,&extra,1);closed=rv_native_close(fd);
    return ok&&n==0&&!closed&&card(after)&&pn_equal(before,after,16)&&
        pn_equal(raw,"GXRC3401",8)&&get32(raw+8)==0&&crc(raw,12)==get32(raw+12);
}
static void binding(uint8_t *p)
{
    RvRoot *r=RV_PTR(ctx->root_address);
    p32(p,r->epoch[RV_BOOT_E]);p32(p+4,r->epoch[RV_UNIT_E]);
    p32(p+8,r->epoch[RV_LINK_E]);p32(p+12,r->epoch[RV_MODE_E]);
}
void ig_bx_init(RvPrivateContext *c)
{
    RvRoot *r=RV_PTR(c->root_address);RvSession *s=RV_PTR(c->session_address);unsigned i;
    ctx=c;log_bytes=RV_PTR(c->state_address+2048);pn_zero(log_bytes,4096);
    pn_copy(log_bytes,"GXB03501",8);p16(log_bytes+8,2);p16(log_bytes+10,128);p32(log_bytes+12,4096);
    binding(log_bytes+20);p32(log_bytes+36,r->lease);p32(log_bytes+40,r->entry_serial);
    pn_copy(log_bytes+56,&s->unit,8);p16(log_bytes+64,s->unit.main_version);p16(log_bytes+66,s->unit.cmp_version);
    p32(log_bytes+68,s->generation);pn_copy(log_bytes+72,RV_PTR(s->image_address+80),32);
    for(i=1;i<=2;i++){
        uint8_t *p=log_bytes+128*i;pn_copy(p,i==1?"GXRI3401":"GXRU3401",8);
        p16(p+8,1);p16(p+10,128);p32(p+12,r->entry_serial);
        binding(p+56);pn_copy(p+72,&s->unit,8);
        p16(p+80,s->unit.main_version);p16(p+82,s->unit.cmp_version);
        pn_copy(p+84,RV_PTR(s->image_address+80),32);
    }
    log_bytes[128+22]=(uint8_t)s->selected_source;p32(log_bytes+128+24,s->generation);
    p32(log_bytes+128+28,s->image_bytes);p32(log_bytes+128+32,s->crc);
    ig_bx_event(1,0,s->selected_source,s->generation,r->flags,0);
    ig_bx_event(9,5,r->block,r->block_bytes,c->state_bytes,RV_OK);
}
void ig_bx_event(unsigned event,unsigned phase,uint32_t a,uint32_t b,uint32_t c,int32_t result)
{
    uint32_t seq;uint8_t *p;
    if(!log_bytes)return;
    seq=get32(log_bytes+44);if(seq==UINT32_MAX)return;
    p=log_bytes+384+32*(seq&63);++seq;p32(log_bytes+44,seq);
    if(seq>64)p32(log_bytes+48,seq-64);
    p32(p,seq);p16(p+4,event);p[6]=(uint8_t)phase;p[7]=0;
    p32(p+8,a);p32(p+12,b);p32(p+16,c);p32(p+20,(uint32_t)result);
    p32(p+24,0);p32(p+28,0);
}
void ig_bx_receipt(unsigned install,int32_t status,unsigned stage)
{
    RvSession *s;uint8_t *p;
    if(!log_bytes)return;
    s=RV_PTR(ctx->session_address);p=log_bytes+(install?128:256);
    p32(p+16,(uint32_t)status);p16(p+20,stage);
    p32(p+116,((RvRoot *)RV_PTR(ctx->root_address))->flags);
    if(!install){
        uint32_t array=RV_WORD(0x205a27d8),count=RV_BYTE(0x205a27d4);
        p16(p+28,s->rows);p16(p+30,s->cursor+1);p32(p+120,s->generation);
        p[34]=RV_BYTE(0x205a280f);p[35]=(uint8_t)count;p32(p+48,array);
        if(array==RV_NATIVE_VIEWS&&count>=1&&count<=2){p[32]=RV_BYTE(array);p[33]=RV_BYTE(array+8*(count-1));p32(p+52,RV_WORD(array+8*(count-1)+4));}
    }
    ig_bx_event(install?2:3,stage,s->rows,s->cursor,0,status);
}
/* Fixed native slots only. This record never follows an untrusted table or view pointer. */
void ig_bx_seed(void)
{
    uint8_t *p;
    if(!log_bytes)return;
    p=log_bytes+2432;pn_copy(p,"GXSD3501",8);
    p32(p+8,ctx->ui_state_capacity);
    p32(p+12,RV_WORD(0x2022f5a8));p32(p+16,RV_BYTE(0x2022f5ac));
    p32(p+20,RV_WORD(0x205a27d8));p32(p+24,RV_BYTE(0x205a27d4));
    pn_copy(p+28,RV_PTR(0x2022f71c),32);
    p32(p+32,RV_WORD(0x2022f720));p32(p+60,get32(log_bytes+44));
    if(!log_bytes[2496])pn_copy(log_bytes+2496,p,64);
}
/* Read complete slots through EOF and close. A corrupt/incomplete slot has no generation. */
static int slot(const char *path,uint32_t *generation,int compare,const uint32_t id[4])
{
    uint8_t buf[128],extra;uint32_t after[4],payload=~0u,expected=0;unsigned block,at;int32_t fd,n;int ok=1;
    fd=rv_native_open(path,0);if(fd<0)return 0;
    for(block=0;ok&&block<32;block++){
        at=0;while(at<128){n=rv_native_read(fd,buf+at,128-at);if(n<=0||(unsigned)n>128-at){ok=0;break;}at+=(unsigned)n;}
        if(!ok)break;
        if(compare&&!pn_equal(buf,log_bytes+128*block,128)){ok=0;break;}
        if(!block){
            if(!pn_equal(buf,"GXB03501\0\2\0\200\0\0\20\0",16)||crc(buf,124)!=get32(buf+124)){ok=0;break;}
            *generation=get32(buf+16);expected=get32(buf+52);
        }else{
            payload=gxr2_crc_add(payload,buf,128);
            if(block<=2&&(!pn_equal(buf,block==1?"GXRI3401":"GXRU3401",8)||crc(buf,124)!=get32(buf+124)))ok=0;
        }
    }
    n=rv_native_read(fd,&extra,1);if(n!=0)ok=0;
    if(rv_native_close(fd))ok=0;
    return ok&&~payload==expected&&card(after)&&pn_equal(after,id,16);
}
static void sticky_put(uint8_t *p,const char *magic)
{ pn_zero(p,128);pn_copy(p,magic,8);p[8]=1; }
void ig_bx_unit(int rejected,int32_t status)
{
    RvRoot *r;RvSession *s;uint8_t *p;
    if(!ctx||!log_bytes)return;
    p=log_bytes+2560;
    if(p[8]&&p[9]&&rejected)return;
    r=RV_PTR(ctx->root_address);s=RV_PTR(ctx->session_address);
    sticky_put(p,"GXUL3601");p[9]=rejected?1:0;
    p32(p+12,s->generation);p32(p+16,s->selected_source);p32(p+20,r->state);p32(p+24,r->flags);
    p32(p+28,r->diag_early);p32(p+32,r->check_failure);pn_copy(p+36,&s->unit,8);
    p16(p+44,s->unit.main_version);p16(p+46,s->unit.cmp_version);p32(p+48,(uint32_t)status);
    p32(p+52,RV_WORD(0x2040f804));
}
void ig_bx_apply(uint32_t key,uint32_t caller,uint32_t keep,uint32_t slot,int32_t status,uint32_t t_obs,uint32_t wcount)
{
    RvRoot *r;uint8_t *first,*latest;uint32_t n;
    if(!ctx||!log_bytes)return;
    r=RV_PTR(ctx->root_address);first=log_bytes+2688;latest=log_bytes+2816;
    n=get32(log_bytes+2944)+1;if(n==0)return;p32(log_bytes+2944,n);
    if(!first[8]){
        sticky_put(first,"GXAP3601");
        p32(first+12,n);p32(first+16,key);p32(first+20,caller);p32(first+24,keep);p32(first+28,slot);
        p32(first+32,r->diag_early);p32(first+36,(uint32_t)status);p32(first+40,t_obs);p32(first+44,wcount);
    }
    sticky_put(latest,"GXAP3601");
    p32(latest+12,n);p32(latest+16,key);p32(latest+20,caller);p32(latest+24,keep);p32(latest+28,slot);
    p32(latest+32,r->diag_early);p32(latest+36,(uint32_t)status);p32(latest+40,t_obs);p32(latest+44,wcount);
}
static int measure(const char *path,uint32_t *length)
{
    uint8_t buf[256];uint32_t total=0;int32_t fd,n;
    fd=rv_native_open(path,0);if(fd<0)return 0;
    while(total<4097){
        n=rv_native_read(fd,buf,256);if(n<0){rv_native_close(fd);return -1;}if(!n)break;
        total+=(uint32_t)n;
    }
    if(rv_native_close(fd))return -1;
    *length=total;return 1;
}
int ig_bx_flush(unsigned reason)
{
    return 0; /* Review-only: no black-box media writes. */
    static const char paths[2][18]={"/ATA1/GXRBX0.BIN","/ATA1/GXRBX1.BIN"};
    RvRoot *r;RvSession *s;uint32_t id[4],after[4],gen[2]={0,0},checked;unsigned target,at=0,i;int valid[2],ok=1;int32_t fd,n;
    if(!ctx||!log_bytes||reason<1||reason>3)return 0;
    r=RV_PTR(ctx->root_address);s=RV_PTR(ctx->session_address);
    if(r->block!=ctx->session_address||!r->inflight||(r->state!=RV_READY&&r->state!=RV_VALIDATED)||s->rpc_token||(r->flags&(RF_OWNER|RF_STOP))||rv_native_context()!=0||!card(id))return 0;
    valid[0]=slot(paths[0],&gen[0],0,id);valid[1]=slot(paths[1],&gen[1],0,id);
    if(!valid[0])gen[0]=0;
    if(!valid[1])gen[1]=0;
    target=!valid[0]?0:!valid[1]?1:gen[0]<=gen[1]?0:1;
    checked=gen[0]>gen[1]?gen[0]:gen[1];if(checked==UINT32_MAX)return 0;
    ig_bx_event(4,reason,checked+1,target,0,0);p32(log_bytes+16,checked+1);
    pn_copy(log_bytes+104,id,16);pn_copy(log_bytes+168,id,16);p32(log_bytes+120,r->flags);
    for(i=1;i<=2;i++)p32(log_bytes+128*i+124,crc(log_bytes+128*i,124));
    p32(log_bytes+52,crc(log_bytes+128,3968));p32(log_bytes+124,crc(log_bytes,124));
    if(!card(after)||!pn_equal(id,after,16))return 0;
    {uint32_t len=0;int present=measure(paths[target],&len);
     if(present<0)return 0;
     if(present&&len==4096)fd=rv_native_open(paths[target],2);
     else if(!present)fd=rv_native_create(paths[target],2);
     else return 0;}
    if(fd<0)return 0;
    while(at<4096){
        if(!card(after)||!pn_equal(id,after,16)){ok=0;break;}
        n=rv_native_write(fd,log_bytes+at,4096-at);if(n<=0||(unsigned)n>4096-at){ok=0;break;}at+=(unsigned)n;
    }
    if(rv_native_close(fd))ok=0;
    return ok&&slot(paths[target],&checked,1,id);
}
