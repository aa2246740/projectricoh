#include "gxrce.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static unsigned get16(const uint8_t *p) { return (unsigned)p[0]<<8 | p[1]; }
static uint32_t get32(const uint8_t *p)
{ return (uint32_t)p[0]<<24 | (uint32_t)p[1]<<16 | (uint32_t)p[2]<<8 | p[3]; }
static void put32(uint8_t *p,uint32_t v)
{ p[0]=(uint8_t)(v>>24); p[1]=(uint8_t)(v>>16); p[2]=(uint8_t)(v>>8); p[3]=(uint8_t)v; }
static int readn(FILE *f,uint8_t *p,size_t n) { return fread(p,1,n,f)==n; }
static void trust_decode(const uint8_t *b,Gxr2Trust *t)
{
    unsigned i;
    memcpy(t->body_sha256,b+8,32); memcpy(t->resident_build_id,b+40,32); memcpy(t->resident_abi_id,b+72,16);
    for(i=0;i<3;++i) {
        const uint8_t *r=b+88+48*i;
        memcpy(t->modules[i].unit.name,r,8); t->modules[i].unit.main_version=(uint16_t)get16(r+8);
        t->modules[i].unit.cmp_version=(uint16_t)get16(r+10);
        t->modules[i].stock_crc32=get32(r+12); memcpy(t->modules[i].stock_sha256,r+16,32);
    }
}
int main(int argc,char **argv)
{
    FILE *f; uint8_t head[12],wire[232],*b; char name[256];
    unsigned count,i,k,n,eg,ef,unit,options; uint32_t length,crc;
    Gxr2Trust trust; Gxr2View gate,full,sentinel; Gxr2Status sg,sf;
    if(argc!=2 || !(f=fopen(argv[1],"rb"))) return 2;
    if(!readn(f,head,12) || memcmp(head,"GXR2TEST",8)) return 2;
    count=get32(head+8); memset(&sentinel,0xa5,sizeof(sentinel));
    for(i=0;i<count;++i) {
        if(!readn(f,head,12)) return 2;
        n=get16(head); eg=get16(head+2); ef=get16(head+4); unit=get16(head+6); options=get32(head+8);
        if(n>=sizeof(name) || unit>=3 || !readn(f,(uint8_t *)name,n)) return 2;
        name[n]=0;
        if(!readn(f,head,4) || !readn(f,wire,232)) return 2;
        length=get32(head); if(length>GXR2_MAX_FILE+1) return 2;
        b=malloc(length?length:1); if(!b || !readn(f,b,length)) return 2;
        trust_decode(wire,&trust); crc=gxr2_crc32(b,length); gate=sentinel; full=sentinel;
        sg=gxr2_gate_validate(b,length,&trust,&trust.modules[unit].unit,options,&gate);
        sf=gxr2_validate(b,length,&trust,&trust.modules[unit].unit,options,&full);
        if((unsigned)sg!=eg || (unsigned)sf!=ef || crc!=gxr2_crc32(b,length) ||
           (sg!=GXR2_OK && memcmp(&gate,&sentinel,sizeof(gate))) ||
           (sf!=GXR2_OK && memcmp(&full,&sentinel,sizeof(full)))) {
            fprintf(stderr,"FAIL %s gate=%s expected=%u full=%s expected=%u\n",name,gxr2_status_name(sg),eg,gxr2_status_name(sf),ef);
            return 1;
        }
        if(sf==GXR2_OK) {
            for(k=0;k<3;++k) if(full.selected_module==k && !full.semantic) return 1;
            if(full.executable) {
                uint8_t *relocated=malloc(length); Gxr2View initialized;
                if(!relocated) return 2;
                memcpy(relocated,b,length);
                for(k=0;k<get16(b+120);++k) {
                    const uint8_t *r=b+gate.sections[1].offset+8u*k;
                    put32(relocated+get32(r),UINT32_C(0x10000000)+get32(r+4));
                }
                gate.bytes=relocated;
                if(gxr2_semantic_validate(&gate,&trust,&initialized)!=GXR2_OK || !initialized.semantic) {
                    fprintf(stderr,"FAIL post-relocation pure init %s\n",name); return 1;
                }
                free(relocated);
            }
        }
        free(b);
    }
    if(fgetc(f)!=EOF || ferror(f) || fclose(f)) return 2;
    printf("corpus cases=%u failures=0\n",count); return 0;
}
