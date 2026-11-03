#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include "trace_units.h"
static uintptr_t base;
static uint32_t *limit;
static unsigned active,scenario;
static uint64_t count,fields[5];
static struct {unsigned site;uint32_t address;uint64_t count;} events[128];
static unsigned used;
void trace_config(void *m,uint32_t *end){base=(uintptr_t)m;limit=end;}
void trace_begin(unsigned c){scenario=c;active=1;}
void trace_end(void){active=0;}
void trace_store(void *p,uint64_t n,unsigned site)
{
    uintptr_t x=(uintptr_t)p;uint32_t a;unsigned k=5,i;
    if(!active||!n||x<base||x-base>=0x800000)return;
    a=0x20000000u+(uint32_t)(x-base);
    if(a>=0x20704804u&&a<*limit&&n<=*limit-a)return;
    if(trace_roles[site]==1||trace_roles[site]==2){
        if(a==0x2022f725&&n==1)k=0;
        if(a==0x2022f726&&n==1)k=1;
        if(a==0x2022f5a8&&n==4)k=2;
        if(a==0x2022f5ac&&n==1)k=3;
    }
    if((trace_roles[site]==2||trace_roles[site]==3)&&n==4&&
       (a==0x205a27a0||a==0x205a27a8)&&*(uint8_t *)(base+a-4-0x20000000u)==33)k=4;
    if(k==5){fprintf(stderr,"REJECT native store case=%u address=%08x width=%llu function=%s\n",scenario,a,(unsigned long long)n,trace_names[site]);exit(93);}
    ++count;++fields[k];
    for(i=0;i<used;++i)if(events[i].site==site&&events[i].address==a)break;
    if(i==used){if(used==128)exit(94);events[i].site=site;events[i].address=a;++used;}
    ++events[i].count;
}
void trace_summary(void)
{
    unsigned i;
    for(i=0;i<used;++i)printf("STORE address=%08x count=%llu function=%s\n",events[i].address,
        (unsigned long long)events[i].count,trace_names[events[i].site]);
    printf("TRACE native_stores=%llu four_fields=%llu/%llu/%llu/%llu tag33=%llu other=0\n",
           (unsigned long long)count,(unsigned long long)fields[0],(unsigned long long)fields[1],
           (unsigned long long)fields[2],(unsigned long long)fields[3],(unsigned long long)fields[4]);
}
