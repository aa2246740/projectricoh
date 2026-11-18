#include "fx_kernel.h"

/* Q8.8 nodes, Q0.8 fractions. Equal fractions retain Y, C1, C2 order.
 * Same arithmetic as the probe kernel that was timed on the camera. */
static void pixel(const volatile uint16_t *table, uint32_t y, uint32_t u,
                  uint32_t v, int32_t output[3])
{
    uint32_t f[3]={y&65535u,u&65535u,v&65535u};
    uint32_t step[3]={3,51,867},temporary;
    const volatile uint16_t *a=table+((v>>16)*289u+(u>>16)*17u+(y>>16))*3u;
    const volatile uint16_t *b,*c,*d;
    unsigned channel;
#define SORT(i,j) do { if(f[i]<f[j]) { temporary=f[i]; f[i]=f[j]; f[j]=temporary; \
    temporary=step[i]; step[i]=step[j]; step[j]=temporary; } } while(0)
    SORT(0,1); SORT(1,2); SORT(0,1);
#undef SORT
    b=a+step[0]; c=b+step[1]; d=c+step[2];
    for(channel=0;channel<3;++channel) {
        int32_t av=a[channel],bv=b[channel],cv=c[channel],dv=d[channel];
        output[channel]=(av<<8)+(int32_t)f[0]*(bv-av)+
            (int32_t)f[1]*(cv-bv)+(int32_t)f[2]*(dv-cv);
    }
}
static uint32_t clip(uint32_t value) { return value>255u?255u:value; }

/* Compiled separately without LTO. Both pixels always visit four vertices,
 * including equal Y values. */
__attribute__((noinline))
void lr_kernel(const uint32_t *source, uint32_t *destination, uint32_t pairs,
               const volatile uint16_t *table, const uint32_t *coordinates)
{
    while(pairs--) {
        uint32_t input=*source++,u=coordinates[(input>>8)&255u],v=coordinates[input&255u];
        int32_t a[3],b[3];
        uint32_t y0,y1,c1,c2;
        pixel(table,coordinates[input>>24],u,v,a);
        pixel(table,coordinates[(input>>16)&255u],u,v,b);
        y0=clip((uint32_t)(a[0]+32768)>>16);
        y1=clip((uint32_t)(b[0]+32768)>>16);
        c1=clip((uint32_t)(a[1]+b[1]+65536)>>17);
        c2=clip((uint32_t)(a[2]+b[2]+65536)>>17);
        *destination++=(y0<<24)|(y1<<16)|(c1<<8)|c2;
    }
}
__attribute__((noinline)) void lr_empty(void) { __asm__ __volatile__("":::"memory"); }
