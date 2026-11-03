#include "kernel.h"

static uint32_t clip(uint32_t x) { return x>255u?255u:x; }

/* Stable descending fractions: equal values retain Y, C2, C3 order. */
static void pixel(const uint16_t *table,uint32_t y,uint32_t c2,uint32_t c3,int32_t out[3])
{
    uint32_t f[3]={y&65535u,c2&65535u,c3&65535u};
    uint32_t stride[3]={3,51,867},t;
    const uint16_t *v0=table+((c3>>16)*289u+(c2>>16)*17u+(y>>16))*3u;
    const uint16_t *v1,*v2,*v3;unsigned c;
#define SWAP(a,b) do { if(f[a]<f[b]) { t=f[a];f[a]=f[b];f[b]=t; \
    t=stride[a];stride[a]=stride[b];stride[b]=t; } } while(0)
    SWAP(0,1);SWAP(1,2);SWAP(0,1);
#undef SWAP
    v1=v0+stride[0];v2=v1+stride[1];v3=v2+stride[2];
    for(c=0;c<3;++c) {
        int32_t a=v0[c],b=v1[c],d=v2[c],e=v3[c];
        out[c]=(a<<8)+(int32_t)f[0]*(b-a)+(int32_t)f[1]*(d-b)+(int32_t)f[2]*(e-d);
    }
}

__attribute__((noinline))
void p0_kernel(uint32_t *buffer,uint32_t pairs,const uint16_t *table,const uint32_t *coord)
{
    while(pairs--) {
        uint32_t in=*buffer,c2=coord[(in>>8)&255u],c3=coord[in&255u];
        int32_t a[3],b[3];uint32_t y0,y1,u,v;
        pixel(table,coord[in>>24],c2,c3,a);
        pixel(table,coord[(in>>16)&255u],c2,c3,b);
        y0=clip((uint32_t)(a[0]+32768)>>16);
        y1=clip((uint32_t)(b[0]+32768)>>16);
        u=clip((uint32_t)(a[1]+b[1]+65536)>>17);
        v=clip((uint32_t)(a[2]+b[2]+65536)>>17);
        *buffer++=(y0<<24)|(y1<<16)|(u<<8)|v;
    }
}
