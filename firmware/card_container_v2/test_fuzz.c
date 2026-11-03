#include "gxrce.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static unsigned be16(const uint8_t *p) { return (unsigned)p[0]<<8|p[1]; }
static uint32_t be32(const uint8_t *p) { return (uint32_t)p[0]<<24|(uint32_t)p[1]<<16|(uint32_t)p[2]<<8|p[3]; }
static void p32(uint8_t *p,uint32_t v) { p[0]=(uint8_t)(v>>24); p[1]=(uint8_t)(v>>16); p[2]=(uint8_t)(v>>8); p[3]=(uint8_t)v; }
int main(int argc,char **argv)
{
    FILE *f; uint8_t *base,*b,wire[232]; Gxr2Trust trust; Gxr2View out,sentinel; Gxr2Status status;
    size_t n,pos; uint32_t rng=UINT32_C(0x53454d32),before; unsigned i,j,rejected=0,accepted=0;
    if(argc!=3) return 2;
    base=malloc(32769); if(!base) return 2;
    f=fopen(argv[1],"rb"); if(!f) return 2; n=fread(base,1,32769,f); if(ferror(f)||fclose(f)||n<256||n>32768) return 2;
    f=fopen(argv[2],"rb"); if(!f) return 2; if(fread(wire,1,232,f)!=232||ferror(f)||fclose(f)) return 2;
    memcpy(trust.body_sha256,wire+8,32); memcpy(trust.resident_build_id,wire+40,32); memcpy(trust.resident_abi_id,wire+72,16);
    for(i=0;i<3;++i) {
        const uint8_t *d=wire+88+48*i;
        memcpy(trust.modules[i].unit.name,d,8); trust.modules[i].unit.main_version=(uint16_t)be16(d+8);
        trust.modules[i].unit.cmp_version=(uint16_t)be16(d+10); trust.modules[i].stock_crc32=be32(d+12);
        memcpy(trust.modules[i].stock_sha256,d+16,32);
    }
    memset(&sentinel,0xa5,sizeof(sentinel));
    for(i=0;i<4096;++i) {
        b=malloc(n); if(!b) return 2; memcpy(b,base,n);
        for(j=0;j<1u+i%4u;++j) {
            rng^=rng<<13; rng^=rng>>17; rng^=rng<<5; pos=rng%n;
            b[pos]^=(uint8_t)(1u<<(rng%8));
        }
        /* Repair outer CRCs so structural/semantic checks see hostile fields. */
        p32(b+24,gxr2_crc32(b+256,n-256)); p32(b+20,0); p32(b+20,gxr2_crc32(b,256));
        before=gxr2_crc32(b,n); out=sentinel;
        status=gxr2_validate(b,n,&trust,&trust.modules[0].unit,GXR2_HOST_ONLY,&out);
        if(status==GXR2_OK) ++accepted;
        else { ++rejected; if(memcmp(&out,&sentinel,sizeof(out))) return 1; }
        if(before!=gxr2_crc32(b,n)) return 1;
        free(b);
    }
    free(base);
    printf("resealed_mutations=4096 accepted=%u rejected=%u failures=0\n",accepted,rejected); return 0;
}
