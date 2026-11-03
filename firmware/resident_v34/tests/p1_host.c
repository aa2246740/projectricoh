#include "resident.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static uint8_t ram[0x800000],ctl[16];
static uint32_t frame[64],checks,cases,opens,reads,closes,allocs,engines,ids;
static int present,short_read,extra_read,close_error,id_error,id_change,read_error;
static unsigned read_index;
RvRoot *rv_host_root;
const RvTrust rv_trust={0};
const uint32_t rv_pins[3]={0xf09fe7b4,0xfb3fbcb2,0x95f3dca9};
const uint8_t rv_skip_01[4]={0},rv_skip_02[4]={0},rv_skip_05[4]={0},
    rv_skip_06[4]={0},rv_skip_07[4]={0},rv_skip_08[4]={0},rv_close_07[4]={0};
#define CHECK(x) do {++checks;if(!(x)){fprintf(stderr,"FAIL line %u: %s\n",__LINE__,#x);exit(1);}}while(0)
#define CASE() (++cases)

void *rv_host_address(uint32_t a)
{CHECK(a>=0x20000000&&a<0x20800000);return ram+(a-0x20000000);}
void rv_clear(void *p,uint32_t n){memset(p,0,n);}
int rv_equal(const void *a,const void *b,uint32_t n){return !memcmp(a,b,n);}
uint32_t rv_be32(const uint8_t *p)
{return (uint32_t)p[0]<<24|(uint32_t)p[1]<<16|(uint32_t)p[2]<<8|p[3];}
uint32_t rv_irq_save(void){return 0xc1;}
void rv_irq_restore(uint32_t irq){CHECK(irq==0xc1);}
void rv_cache_sync(void){}
int32_t rv_native_open(const char *path,uint32_t mode)
{++opens;CHECK(!strcmp(path,"/ATA1/GXRCE.CTL")&&!mode);read_index=0;return present?7:-1;}
int32_t rv_native_read(int32_t fd,void *out,uint32_t n)
{
    ++reads;CHECK(fd==7);
    if(!read_index++){
        CHECK(n==16);if(read_error)return -1;
        memcpy(out,ctl,short_read?short_read:16);return short_read?short_read:16;
    }
    CHECK(n==1);return extra_read;
}
int32_t rv_native_close(int32_t fd){++closes;CHECK(fd==7);return close_error;}
uint32_t rv_native_alloc(uint32_t n){++allocs;CHECK(n>0);return 0;}
void rv_native_free(uint32_t a){(void)a;CHECK(0);}
int32_t rv_native_sd_id(void *out)
{uint32_t id[4]={1,2,3,4};++ids;if(id_change&&ids>1)id[0]=5;memcpy(out,id,16);return id_error;}
int32_t rv_native_layer(uint32_t a,uint32_t b,uint32_t c)
{(void)a;(void)b;(void)c;CHECK(0);return -1;}
int32_t rv_invoke(uint32_t a,const RvApi *b,uint32_t c,const RvRequest *d,RvReply *e)
{(void)a;(void)b;(void)c;(void)d;(void)e;++engines;CHECK(0);return RV_FAULT;}

static void counts(void){opens=reads=closes=allocs=engines=ids=0;read_index=0;}
static void control(unsigned mode)
{
    memset(ctl,0,16);memcpy(ctl,"GXRC3401",8);rv_put32(ctl+8,mode);
    rv_put32(ctl+12,gxrce_crc32(ctl,12));present=1;
    short_read=extra_read=close_error=id_error=id_change=read_error=0;counts();
}
static void setup(unsigned unit)
{
    static const char names[3][8]={"jlaunch","qlaunch","l08firm"};
    memset(ram,0,sizeof(ram));memset(frame,0,sizeof(frame));
    rv_host_root=RV_PTR(RV_ROOT);memset(rv_host_root,255,244);
    memcpy(rv_host_root->pins,rv_pins,12);
    RV_WORD(0x200d3488)=0x20480000;RV_WORD(0x200d348c)=0x207ffff0;
    RV_WORD(0x200c0dac)=0x20500000;RV_WORD(0x200c0db0)=4096;
    RV_BYTE(0x2050036e)=1;RV_WORD(0x2040f804)=1;
    memcpy(RV_PTR(0x2040f81c),names[unit],8);
    memcpy(RV_PTR(0x2040f848),"\1\121\0\0",4);
    RV_WORD(0x200d7fd8)=1;((uint8_t *)RV_PTR(0x200d8000))[1]=9;
    RV_WORD(0x2022f5a8)=0x2022d610;RV_BYTE(0x2022f5ac)=7;
    RV_WORD(0x205a27d8)=RV_NATIVE_VIEWS;RV_BYTE(0x205a27d4)=1;
    RV_BYTE(RV_NATIVE_VIEWS)=32;RV_WORD(0x205d9bf8)=8;
    RV_BYTE(0x205a280f)=2;control(1);counts();
}
static void tick(uint32_t table,unsigned index,unsigned state,unsigned next)
{
    frame[2]=1;frame[3]=table;frame[4]=next;frame[5]=frame[7]=0;frame[6]=index;
    RV_WORD(0x205d9c00)=state;
    rv_hook_observe(rv_host_root,40,frame);
}
static void ready(unsigned unit)
{
    setup(unit);tick(0,0,0,1);tick(0x20378d94,0,2,1);
    tick(0x20378e00,0,2,0);tick(0x20378e00,2,32,1);
    tick(0x203753b0,0,5,1);tick(0x2037550c,0,5,0);
    CHECK((rv_host_root->flags&RF_READY_MASK)==(5u<<RF_READY_SHIFT));
    CHECK(!(rv_host_root->flags&RF_STOP));
}
static void key(unsigned edge,unsigned raw)
{
    uint8_t *msg=(uint8_t *)(frame+17)+28;
    msg[6]=0x70;msg[7]=0x0b;rv_put32(msg+12,raw);rv_put32(msg+16,edge);
    tick(raw==0x17?0x2037550c:0x203761e0,3,56,1);
}
static void inert(void)
{
    unsigned h;uint8_t saved[128];memcpy(saved,RV_PTR(0x20510000),sizeof(saved));
    for(h=1;h<=9;++h)rv_hook_observe(rv_host_root,h,frame);
    CHECK(!opens&&!reads&&!closes&&!allocs&&!engines&&!ids);
    CHECK(!memcmp(saved,RV_PTR(0x20510000),sizeof(saved)));
}
static void gate_tests(void)
{
    unsigned u,k;RvRoot *r;
    for(u=0;u<3;++u){
        CASE();setup(u);inert();ready(u);inert();key(1,0x17);r=rv_host_root;
        CHECK(r->permit.nonce);CHECK(rv_take_permit(r));CHECK(!r->permit.nonce);
        CHECK(!rv_take_permit(r));CHECK(!opens&&!allocs&&!engines);
        for(k=0;k<3;++k){
            CASE();ready(u);key(k,0x17);CHECK(!!rv_host_root->permit.nonce==(k==1));
            CASE();ready(u);key(k,0x11);CHECK(!!rv_host_root->permit.nonce==(k==1));
        }
        CASE();ready(u);key(1,0x17);tick(0x2037550c,1,5,0);CHECK(!rv_host_root->permit.nonce);inert();
        CASE();ready(u);key(1,0x17);RV_BYTE(0x205a280f)=1;key(1,0x17);CHECK(!rv_host_root->permit.nonce);
        CASE();ready(u);RV_WORD(0x205d9bf8)=7;key(1,0x17);CHECK(!rv_host_root->permit.nonce);
        CASE();setup(u);tick(0,0,0,1);tick(0x2037550c,0,5,0);key(1,0x17);CHECK(!rv_host_root->permit.nonce);inert();
        for(k=0;k<6;++k){
            CASE();ready(u);key(1,0x17);r=rv_host_root;
            if(k==0)RV_WORD(0x2040f804)=0;
            if(k==1)RV_BYTE(0x2040f81c)^=1;
            if(k==2)RV_WORD(0x200d3488)+=4;
            if(k==3)RV_WORD(0x200c0dac)+=4;
            if(k==4)RV_BYTE(0x205d9a7f)=4;
            if(k==5)RV_BYTE(0x2050036e)=3;
            tick(0x2037550c,3,56,1);CHECK(!r->permit.nonce&&(r->flags&RF_STOP));
            CHECK(!(r->flags&RF_GRANTS));counts();inert();
        }
        CASE();ready(u);key(1,0x17);r=rv_host_root;++r->epoch[RV_UNIT_E];CHECK(!rv_take_permit(r));inert();
        CASE();ready(u);key(1,0x17);r=rv_host_root;r->flags|=RF_SESSION;
        k=r->epoch[RV_BOOT_E];tick(0,0,0,1);CHECK(r->epoch[RV_BOOT_E]==k+1);
        CHECK(!r->permit.nonce&&!(r->flags&RF_GRANTS));inert();
        CASE();ready(u);r=rv_host_root;r->rx=~0u;key(1,0x17);CHECK(r->flags&RF_STOP);inert();
        CASE();ready(u);r=rv_host_root;r->next_token=~0u;key(1,0x17);CHECK(r->flags&RF_STOP);inert();
        CASE();ready(u);r=rv_host_root;r->epoch[RV_BOOT_E]=~0u;tick(0,0,0,1);CHECK(r->flags&RF_STOP);inert();
        CASE();ready(u);RV_WORD(0x20375674)=0xa8;tick(0x2037550c,30,5,0);
        CHECK(rv_host_root->flags&RF_STOP);key(1,0x17);CHECK(!rv_host_root->permit.nonce);inert();
        CASE();ready(u);key(1,0x17);control(0);rv_hook_observe(rv_host_root,1,frame);
        CHECK(opens==1&&reads==2&&closes==1&&!allocs&&!engines);
        CHECK(rv_host_root->state==RV_DISABLED_UNTIL_REBOOT);counts();inert();
        CASE();ready(u);key(1,0x17);control(1);present=0;rv_hook_observe(rv_host_root,1,frame);
        CHECK(opens==1&&allocs==1&&!engines);
        CASE();ready(u);key(1,0x17);control(0);read_error=1;rv_hook_observe(rv_host_root,1,frame);
        CHECK(opens==1&&allocs==1&&!engines);
    }
}
static void control_tests(void)
{
    unsigned i;
    CASE();control(0);CHECK(rv_control_off()==1);
    CASE();control(1);CHECK(rv_control_off()==0);
    CASE();control(0);present=0;CHECK(rv_control_off()==0);
    CASE();control(0);read_error=1;CHECK(rv_control_off()==0);
    CASE();control(0);extra_read=1;CHECK(rv_control_off()==0);
    CASE();control(0);close_error=-1;CHECK(rv_control_off()==0);
    CASE();control(0);id_error=-1;CHECK(rv_control_off()==0);
    CASE();control(0);id_change=1;CHECK(rv_control_off()==0);
    for(i=1;i<16;++i){CASE();control(0);short_read=i;CHECK(rv_control_off()==0);}
    for(i=0;i<16;++i){CASE();control(0);ctl[i]^=1;CHECK(rv_control_off()==0);}
}
int main(void)
{
    gate_tests();control_tests();
    printf("PASS P1 unit fixtures: cases=%u assertions=%u; native boundaries are doubles; no product/continuous replay\n",cases,checks);
    return 0;
}
