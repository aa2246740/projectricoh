#include "eng_internal.h"
int eng_grain_gate(const volatile EngGrain *r,const EngEpoch *e,unsigned category,
                  const uint8_t *s,size_t sn,uint8_t *p,size_t pn)
{
    unsigned size,level;
    if(!r || !e || !s || !p || sn<0xc9e || pn<0x90 || r->armed!=1 ||
       r->boot!=e->boot || r->heap!=e->heap || r->link!=e->link || r->unit!=e->unit ||
       r->settings!=e->settings || r->mode!=e->mode || !(r->recipe&(ENG_GRAIN<<8)) ||
       (category!=0 && category!=4) || s[0x36e]!=(r->recipe&255) ||
       (p[0x1a]|p[0x14]|p[0x75]|p[0x1e]|p[0x26])) return 0;
    size=s[0x3aa]; if(size>16 || !((UINT32_C(0x11126)>>size)&1)) return 0;
    /* Recheck publication before touching the packet. The resident must call
     * this in its own snapshot/epoch critical section, never via heap code. */
    if(r->armed!=1) return 0;
    p[0x1a]=21; p[0x10]=0; p[0x32]=1; level=s[0xc9d];
    p[0x6f]=(uint8_t)(level>=1 && level<=3?level:1); return 1;
}
