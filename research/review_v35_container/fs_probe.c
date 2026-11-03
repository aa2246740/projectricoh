/* Actual frozen blackbox.c, FAT-like boundary. This is not a FAT emulator. */
#define RV_HOST 1
#define ENG_HOST 1
#ifndef REVIEW_BLACKBOX_SOURCE
#define REVIEW_BLACKBOX_SOURCE "isolated/candidate/containers/product/blackbox.c"
#endif
#include REVIEW_BLACKBOX_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static _Alignas(16) unsigned char ram[0x800000];
static struct {char path[32];unsigned char data[5000];unsigned n;} ent[12];
static struct {int live,e;unsigned pos;} fd[2];
static unsigned ec,creates,writes,open0,transient,persistent,partial,readonly;
void *rv_host_address(uint32_t a){if(a<0x20000000u||a>=0x20800000u)abort();return ram+(a-0x20000000u);}
void pn_zero(void *p,uint32_t n){memset(p,0,n);}
void pn_copy(void *p,const void *q,uint32_t n){memcpy(p,q,n);}
int pn_equal(const void *p,const void *q,uint32_t n){return !memcmp(p,q,n);}
uint32_t gxr2_crc_add(uint32_t c,const uint8_t *p,size_t n)
{size_t i;unsigned j;for(i=0;i<n;i++){c^=p[i];for(j=0;j<8;j++)c=(c>>1)^(0xedb88320u&-(c&1u));}return c;}
uint32_t gxr2_crc32(const uint8_t *p,size_t n){return ~gxr2_crc_add(~0u,p,n);}
int32_t rv_native_sd_id(void *p){static const uint32_t id[4]={1,2,3,4};memcpy(p,id,16);return 0;}
int32_t rv_native_context(void){return 0;}
static int find(const char *p){unsigned i;for(i=0;i<ec;i++)if(!strcmp(ent[i].path,p))return (int)i;return -1;}
static int openent(int e){unsigned i;for(i=0;i<2&&fd[i].live;i++){}if(i==2)return -1;fd[i].live=1;fd[i].e=e;fd[i].pos=0;return i+17;}
int32_t rv_native_open(const char *p,uint32_t f)
{int e=find(p);if(!strcmp(p,"/ATA1/GXRBX0.BIN")){++open0;if(persistent||(transient&&open0==2)){printf("inject open=-1 flags=%u call=%u\n",f,open0);return -1;}}return e<0?-1:openent(e);}
int32_t rv_native_create(const char *p,uint32_t f)
{int old=find(p);(void)f;++creates;printf("create existing=%d new=%u\n",old,ec);if(readonly)return -1;if(ec==12)abort();strcpy(ent[ec].path,p);ent[ec].n=0;return openent(ec++);}
int32_t rv_native_read(int32_t f,void *p,uint32_t n)
{unsigned k;int i=f-17,e=fd[i].e;if(!fd[i].live)abort();k=ent[e].n-fd[i].pos;if(k>n)k=n;memcpy(p,ent[e].data+fd[i].pos,k);fd[i].pos+=k;return k;}
int32_t rv_native_write(int32_t f,const void *p,uint32_t n)
{int i=f-17,e=fd[i].e;if(!fd[i].live)abort();if(readonly)return -1;if(partial&&writes)return -1;if(partial&&n>512)n=512;if(fd[i].pos+n>sizeof(ent[e].data))abort();memcpy(ent[e].data+fd[i].pos,p,n);fd[i].pos+=n;if(fd[i].pos>ent[e].n)ent[e].n=fd[i].pos;++writes;return n;}
int32_t rv_native_close(int32_t f){if(!fd[f-17].live)abort();fd[f-17].live=0;return 0;}
static void put(const char *p,unsigned n,unsigned byte){strcpy(ent[ec].path,p);memset(ent[ec].data,byte,n);ent[ec++].n=n;}
int main(int argc,char **argv)
{RvRoot *r;RvSession *s;RvPrivateContext c={0};unsigned size=4096,i,dups=0;int result;
 if(argc!=2)return 2;r=RV_PTR(0x20001000);s=RV_PTR(0x20002000);c.root_address=0x20001000;c.session_address=0x20002000;c.state_address=0x20010000;r->block=c.session_address;r->inflight=1;r->state=RV_READY;s->image_address=0x20020000;s->generation=116;
 transient=!strcmp(argv[1],"transient");persistent=!strcmp(argv[1],"persistent");readonly=!strcmp(argv[1],"readonly");partial=!strcmp(argv[1],"partial");
 if(!strcmp(argv[1],"short"))size=4095;if(!strcmp(argv[1],"long"))size=4097;
 if(strcmp(argv[1],"absent"))put("/ATA1/GXRBX0.BIN",size,0x5a);
 if(!strcmp(argv[1],"duplicate"))put("/ATA1/GXRBX0.BIN",4096,0xa5);
 memset(RV_PTR(c.state_address+2048-8),0xa5,8);memset(RV_PTR(c.state_address+2048+4096),0xa5,8);
 ig_bx_init(&c);ig_bx_unit(0,0);ig_bx_apply(1,2,3,4,0,2,99);
 if(!strcmp(argv[1],"bounds")){unsigned k;uint8_t first[128];memcpy(first,log_bytes+2688,128);
   for(k=0;k<5000;k++)ig_bx_event(8,2,k,k+1,k+2,-1);
   for(k=0;k<127;k++)ig_bx_apply(k,2,3,4,-1,0xffffffffu,k);
   if(memcmp(first,log_bytes+2688,128)||get32(log_bytes+2944)!=128||get32(log_bytes+2816+12)!=128)abort();
 }
 if(!strcmp(argv[1],"validated"))r->state=RV_VALIDATED;
 result=ig_bx_flush(1);
 for(i=0;i<8;i++)if(RV_BYTE(c.state_address+2048-8+i)!=0xa5||RV_BYTE(c.state_address+2048+4096+i)!=0xa5)abort();
 for(i=0;i<ec;i++)if(!strcmp(ent[i].path,"/ATA1/GXRBX0.BIN"))dups++;
 printf("case=%s flush=%d entries=%u same_name=%u create=%u writes=%u first_length=%u first_byte=%02x\n",argv[1],result,ec,dups,creates,writes,ec?ent[0].n:0,ec?ent[0].data[0]:0);
 if(!strcmp(argv[1],"disabled"))return !(!result&&!creates&&!writes);
 if(transient||persistent)return !(dups==2&&creates==1&&!result);
 if(!strcmp(argv[1],"short")||!strcmp(argv[1],"long"))return !(!result&&!creates&&!writes);
 if(!strcmp(argv[1],"duplicate"))return !(result&&dups==2&&!creates&&ent[1].data[0]==0xa5);
 if(partial)return !(!result&&writes==1&&ent[0].n==4096);
 if(readonly)return !(!result&&!creates&&!writes);
 return !(result&&dups==1);
}
