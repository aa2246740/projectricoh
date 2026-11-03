#define main validator_original_main
#include "../../firmware/engine_fix_r2/containers/product/src/firmware/card_container_v2/validate.c"
#undef main
#include "../../firmware/engine_fix_r2/containers/product/src/firmware/card_container_v2/gxts.h"
static void hex(const uint8_t *p,unsigned n){unsigned i;for(i=0;i<n;i++)printf("%02x",p[i]);}
int main(int argc,char **argv)
{
    Gxr2Trust t;Gxr2View v;GxtsBinding b;uint8_t raw[GXR2_MAX_FILE],e[448];size_t n;unsigned m,s,bank;
    if(argc!=3||!load_trust(argv[2],&t)||!read_file(argv[1],raw,sizeof(raw),&n))return 2;
    for(m=0;m<3;m++){
        if(gxr2_validate(raw,n,&t,&t.modules[m].unit,0,&v)!=GXR2_OK)return 3;
        {const uint8_t *p=raw+v.sections[2].offset+64*m+16;bank=(unsigned)p[0]<<24|(unsigned)p[1]<<16|(unsigned)p[2]<<8|p[3];}
        for(s=1;s<=16;s++){
            if(gxr2_expand(&v,m,s,e)!=GXR2_OK||gxts_bind(&v,m,s,&b)!=GXTS_OK)return 4;
            printf("%u %u ",m,s);hex(e,448);hex(raw+bank+32+64*(s-1),64);hex(b.identity,160);putchar('\n');
        }
    }
    return 0;
}
