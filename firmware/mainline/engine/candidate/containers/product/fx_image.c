/* XPan bars on the native visible OSD plane, hardware scanout buffer,
 * vertical subwindow remapper (122..358), and Bank-0 CLUT across all 3 A12
 * r5 units (qlaunch 28mm, jlaunch 50mm, l08firm MOUNT). Software layer 1
 * keeps index 255 fill/clear. Hardware writes use native 32-bit status
 * handshake at 0xF0218804 bit 15 (0x00008000), rolling back dirty slots on
 * mid-loop busy timeout. Pre-entry CLUT, subwindow, and <=1024 colliding
 * [60,122)/[358,420) scanout indices are saved and restored unconditionally
 * from g185's own dirty state (>1024 rare pixels skip scanout mutation). */
#include "fx_image.h"
#ifdef HF6
#include "hf1.h"
#endif
#include "fx_store.h"
#include "../../engine_services/engine_services.h"
FxImage fx_image;
#define XPAN_BLACK 255u
#define SCAN_RARE_MAX 1024u
/* bit 0: software layer 1 bars active; bit 1: hardware mask active */
static uint32_t mask_active;
typedef struct { uint8_t idx,pad[3]; uint32_t on; } XpanClut;
static const XpanClut xpan_clut[21]={
    {180,{0,0,0},0x08008080u},
    {181,{0,0,0},0x08a08080u},
    {182,{0,0,0},0x08648080u},
    {183,{0,0,0},0x08be8080u},
    {200,{0,0,0},0x08008080u},
    {201,{0,0,0},0x08008080u},
    {202,{0,0,0},0x08a08080u},
    {203,{0,0,0},0x08648080u},
    {207,{0,0,0},0x08008080u},
    {208,{0,0,0},0x08008080u},
    {209,{0,0,0},0x08008080u},
    {210,{0,0,0},0x08008080u},
    {211,{0,0,0},0x08008080u},
    {212,{0,0,0},0x08008080u},
    {218,{0,0,0},0x08008080u},
    {219,{0,0,0},0x08a08080u},
    {220,{0,0,0},0x08648080u},
    {221,{0,0,0},0x08be8080u},
    {222,{0,0,0},0x08008080u},
    {223,{0,0,0},0x08008080u},
    {254,{0,0,0},0x08008080u}
};
typedef struct { uint16_t pos; uint8_t b,val; } ScanRare;
static uint32_t saved_clut[21],saved_subwin[5],clut_dirty_mask;
static ScanRare scan_rare[SCAN_RARE_MAX];
static uint16_t scan_rare_n;
static uint8_t subwin_dirty,scan_dirty;
static uint32_t word(const uint8_t *p)
{return (uint32_t)p[0]<<24|(uint32_t)p[1]<<16|(uint32_t)p[2]<<8|p[3];}
static int bytes_eq(const volatile uint8_t *p,const uint8_t *q,uint32_t n)
{uint32_t i;for(i=0;i<n;++i)if(p[i]!=q[i])return 0;return 1;}
#ifdef G188_R3
__attribute__((noinline))
#endif
static int session_ok(void)
{
    RvRoot *r=RV_PTR(RV_ROOT);uint32_t i;
    if(r->state!=RV_READY||!r->inflight||(r->flags&(RF_STOP|RF_UNCERTAIN))||!fx_store.published)return 0;
    for(i=0;i<12;++i)if(i!=RV_VIEW_E&&i!=RV_S_E&&i!=RV_IO_E&&r->epoch[i]!=fx_store.stamp.epochs[i])return 0;
    return 1;
}
#ifdef G188_R3
__attribute__((noinline))
#endif
static int aspect_169(void)
{
    uint32_t s=RV_WORD(0x200c0dac),n=RV_WORD(0x200c0db0),off;
    if(s<0x20000000u||s>0x207ff000u||n!=0x1000u)return 0;
    off=RV_BYTE(0x205d9a7f)==2?0xa89u:0x3f4u;
    return RV_BYTE(s+off)==2;
}
static int is_xpan_unit(void)
{
    static const uint8_t units[3][8]={
        {'q','l','a','u','n','c','h',0},
        {'j','l','a','u','n','c','h',0},
        {'l','0','8','f','i','r','m',0}
    };
    static const uint8_t mark[4]={0x20,0x7f,0x21,0x7f};
    const volatile uint8_t *u=RV_PTR(0x2040f81cu),*m=RV_PTR(0x2005276cu);
    if(!bytes_eq(u,units[0],8u)&&!bytes_eq(u,units[1],8u)&&!bytes_eq(u,units[2],8u))return 0;
    return bytes_eq(m,mark,4u);
}
static int hw_scan_ok(void)
{
    uint32_t hw=RV_WORD(0x200c0dc8u);
    return hw==0x20744800u&&RV_WORD(0x200c0dccu)==0x177800u&&
           RV_WORD(0x205a19a4u)==hw&&RV_WORD(0x205a1594u)==1u;
}
static int sw_layer1_ok(int require_visible)
{
    uint32_t base=RV_WORD(0x200c0dc8u),i;
    if(base!=0x20744800u||RV_WORD(0x200c0dccu)!=0x177800u||
       RV_WORD(0x205a19a4u)!=base||RV_WORD(0x205a1594u)>1u)return 0;
    if(require_visible&&!(RV_BYTE(0x205a280eu)&1u))return 0;
    for(i=0;i<3u;++i)if(RV_WORD(0x205a1998u+4u*i)!=base+640u+(i+2u)*307200u)return 0;
    return 1;
}
static int clut_wait_ready(void)
{
    uint32_t w;
    for(w=0;w<1024u;++w){
        uint32_t v=RV_WORD(0xf0218804u);
#ifndef ENG_HOST
        __asm__ __volatile__("":"+r"(v));
#endif
        if(!(v&0x00008000u))return 1;
    }
    return 0;
}
static int clut_apply_on(void)
{
    uint32_t i;
    for(i=0;i<21u;++i){
        uint32_t addr=0xf0218000u+4u*(uint32_t)xpan_clut[i].idx;
        if(!clut_wait_ready()){
            if(clut_dirty_mask||subwin_dirty||scan_dirty)fx_mask_hw_restore();
            return 0;
        }
        if(!(clut_dirty_mask&(1u<<i))){
            saved_clut[i]=RV_WORD(addr);
            clut_dirty_mask|=1u<<i;
        }
        RV_WORD(addr)=xpan_clut[i].on;
    }
    return 1;
}
static int is_scan_rare(uint8_t v)
{
    return v==2u||(v>=210u&&v<=212u)||(v>=220u&&v<=222u)||v==254u;
}
static void hw_bars_scan_on(void)
{
    uint32_t b,y,x,first=!scan_dirty;
    if(!hw_scan_ok())return;
    if(first){
        uint32_t n_rare=0u;
        for(b=0;b<2u;++b)for(y=0;y<62u;++y){
            uint32_t base_pos=y*640u;
            volatile uint8_t *row=RV_PTR(0x20744800u+640u*(y+(b?358u:60u)));
            for(x=0;x<640u;++x){
                uint8_t v=row[x];
                if(is_scan_rare(v)){
                    if(n_rare>=SCAN_RARE_MAX){scan_rare_n=0u;return;}
                    scan_rare[n_rare++]=(ScanRare){(uint16_t)(base_pos+x),(uint8_t)b,v};
                }
            }
        }
        scan_rare_n=(uint16_t)n_rare;
        scan_dirty=1u;
    }
    for(b=0;b<2u;++b)for(y=0;y<62u;++y){
        volatile uint8_t *row=RV_PTR(0x20744800u+640u*(y+(b?358u:60u)));
        for(x=0;x<640u;++x){
            uint8_t v=row[x];
            if(first){
                if(v==0u||v==2u)row[x]=254u;
                else if(v==182u)row[x]=220u;
                else if(v==183u)row[x]=221u;
                else if(v==200u)row[x]=222u;
                else if(v>=207u&&v<=209u)row[x]=(uint8_t)(v+3u);
            }else{
                if(v==0u)row[x]=254u;
            }
        }
    }
}
static void hw_bars_scan_off(void)
{
    uint32_t b,y,x,k;
    if(!hw_scan_ok())return;
    for(k=0;k<scan_rare_n;++k){
        uint32_t band=scan_rare[k].b&1u;
        volatile uint8_t *p=RV_PTR(0x20744800u+640u*(band?358u:60u)+scan_rare[k].pos);
        uint8_t want=scan_rare[k].val==2u?254u:scan_rare[k].val;
        if(*p==want)scan_rare[k].b=(uint8_t)(band|0x80u);
    }
    for(b=0;b<2u;++b)for(y=0;y<62u;++y){
        volatile uint8_t *row=RV_PTR(0x20744800u+640u*(y+(b?358u:60u)));
        for(x=0;x<640u;++x){
            uint8_t v=row[x];
            if(v==254u)row[x]=0u;
            else if(v==220u)row[x]=182u;
            else if(v==221u)row[x]=183u;
            else if(v==222u)row[x]=200u;
            else if(v>=210u&&v<=212u)row[x]=(uint8_t)(v-3u);
        }
    }
    for(k=0;k<scan_rare_n;++k){
        if(scan_rare[k].b&0x80u){
            uint32_t band=scan_rare[k].b&1u;
            volatile uint8_t *p=RV_PTR(0x20744800u+640u*(band?358u:60u)+scan_rare[k].pos);
            *p=scan_rare[k].val;
        }
    }
    scan_rare_n=0;scan_dirty=0;
}
static void sw_bars_apply(int on)
{
    uint32_t base=RV_WORD(0x205a1998u),b,y,x,i;
    for(b=0;b<2u;++b)for(y=0;y<122u;++y){
        volatile uint8_t *p=RV_PTR(base+640u*(y+(b?358u:0u)));
        for(x=0;x<80u;++x){
            volatile uint8_t *pixels=p+8u*x;
            volatile uint32_t *words=(volatile uint32_t *)pixels;
            if(on){
                if(words[0]==0xffffffffu&&words[1]==0xffffffffu)continue;
                words[0]=words[1]=0xffffffffu;
            }else{
                uint32_t a=words[0],c=words[1];
                if(!(a|c))continue;
                if(a==0xffffffffu&&c==0xffffffffu){words[0]=words[1]=0;continue;}
                for(i=0;i<8u;++i)if(pixels[i]==XPAN_BLACK)pixels[i]=0;
            }
        }
    }
}
void fx_mask_hw_restore(void)
{
    uint32_t i;
    if(subwin_dirty){
        for(i=0;i<5u;++i)RV_WORD(0x2022936cu+4u*i)=saved_subwin[i];
        subwin_dirty=0;
    }
    if(clut_dirty_mask){
        for(i=0;i<21u;++i){
            if(!(clut_dirty_mask&(1u<<i)))continue;
            if(!clut_wait_ready())break;
            RV_WORD(0xf0218000u+4u*(uint32_t)xpan_clut[i].idx)=saved_clut[i];
            clut_dirty_mask&=~(1u<<i);
        }
    }
    if(scan_dirty)hw_bars_scan_off();
    if(!subwin_dirty&&!clut_dirty_mask&&!scan_dirty)mask_active&=~2u;
}
void fx_mask_suspend(void)
{
    fx_mask_hw_restore();
    if(mask_active&1u){
        if(sw_layer1_ok(0)){sw_bars_apply(0);mask_active&=~1u;}
    }
}
#ifdef XPAN_D2_DIAG
/* Brief section C cuts, all three: dwell is 0/1, the header counters are
 * gone, the K histogram is gone. A record is view, previous view, first
 * action, dwell. Slots fill from 0; once 10 are used the ring shifts and
 * the newest record is slot 9. fx_frame_key sets act on every path and
 * the adapter logs right after it returns, so the first action is the one
 * written when the record opens. The view words are native-only. */
static struct {
    uint8_t ring[40];
    uint8_t n,frozen,act;
    uint8_t xl[7];
} xd;
static void xd_hex2(char *p,uint32_t v)
{static const char d[]="0123456789ABCDEF";p[0]=d[(v>>4)&15u];p[1]=d[v&15u];}
void xd_freeze(void){xd.frozen=1u;}
void xd_log(void)
{
    unsigned m=xd.n<10u?xd.n:10u,i;
    uint8_t view=(uint8_t)RV_WORD(0x205d9c00u),*e;
    if(xd.frozen)return;
    if(m&&view==xd.ring[4u*m-4u]){xd.ring[4u*m-1u]=1u;return;}
    if(m==10u){for(i=0;i<36u;++i)xd.ring[i]=xd.ring[i+4u];m=9u;}
    e=xd.ring+4u*m;
    e[0]=view;e[1]=(uint8_t)RV_WORD(0x205d9c04u);e[2]=xd.act;e[3]=0;
    if(xd.n<255u)++xd.n;
}
void xd_line(unsigned row,char out[14])
{
    unsigned i,m=xd.n<10u?xd.n:10u;
    for(i=0;i<13u;++i)out[i]='.';
    out[13]=0;
    if(!row){out[0]='X';out[1]='D';out[2]='1';xd_hex2(out+3,xd.n);out[12]=xd.frozen?'F':'L';}
    else if(row<6u){
        out[6]=' ';
        for(i=0;i<2u;++i){
            unsigned k=2u*row-2u+i;
            char *p=out+7u*i;
            const uint8_t *e=xd.ring+4u*k;
            if(k<m){xd_hex2(p,e[0]);xd_hex2(p+2,e[1]);p[4]=(char)e[2];p[5]=(char)('0'+e[3]);}
        }
    }else if(row==6u){out[0]='L';if(xd.xl[0])for(i=0;i<6u;++i)xd_hex2(out+1u+2u*i,xd.xl[1u+i]);}
}
#endif
#ifndef G188_R3
/* Same commit conditions for boot and later standby. The native formatter
 * is a body-internal jl: it writes r0-r14, including the r7 a C compiler
 * otherwise keeps across the call. The latch records one commit of the
 * current standby 16:9 scene and is dropped when the view or aspect changes. */
static volatile uint8_t xpan_status_done;
static void status_scene_release(void)
{
    if(RV_WORD(0x205d9c00u)!=5u||!aspect_169())xpan_status_done=0u;
}
#endif
#ifdef XPAN_D123_R1
static volatile uint8_t xpan_label_done;
#endif
__attribute__((noinline)) void xpan_status_redraw(void)
{
#if defined(G188_R3) && !defined(XPAN_D123_R1)
    /* Empty on this profile. The asm barrier is not a load or a store.
     * Without it, LTO deletes the call and then inlines the helpers. */
    __asm__ __volatile__("");
#elif defined(XPAN_D123_R1)
#ifdef XPAN_D1_R2
    /* One redraw of the standby quality/aspect label after the name slot is
     * XPan. The label is icon 70 of the shooting icon table 0x203795D4:
     * part 1, type 57, descriptor 0x2022A680, name table 0x2022A584 whose
     * first entry is 0x20222428. Native keeps its handle as a u16 at
     * 0x205D9CC0 + 2*70 and shows it with 0x201C0CF4(low byte, 0) at
     * 0x202EA05C..0x202EA07C. hide==0 redraws unconditionally. Native does
     * not show icon 70 in display modes 2 and 3 (byte 0x205D9A74, filter
     * tables 0x20379E30 / 0x20379ED4), so those modes do not pass. The latch
     * stays shut after one call. 0x205E4413 (r1) belongs to another screen. */
    uint32_t gates=0,h,m,type=0xffu,hid=0xffu;
    static const uint8_t name[4]={'X','P','a','n'};
    if(xpan_label_done||RV_WORD(0x205d9c00u)!=5u||!aspect_169())return;
    if(!RV_WORD(0x205d9bf8u))gates|=1u;
    if(session_ok())gates|=2u;
    if(bytes_eq((const volatile uint8_t *)RV_PTR(0x20222428u),name,4u))gates|=4u;
    if(RV_BYTE(0x205a280eu)&1u)gates|=8u;
    if(RV_BYTE(0x205a280fu)==1u)gates|=16u;
    h=RV_BYTE(0x205d9d4du);
    m=RV_BYTE(0x205d9a74u);
    if(h>=1u&&h<=RV_BYTE(0x205a27c4u)){
        uint32_t rec=RV_WORD(0x205a27c8u)+8u*(h-1u);
        hid=RV_BYTE(0x205a2416u+h);
        if(rec>=0x20000000u&&rec<=0x207ffff8u&&!(rec&3u)){
            type=RV_BYTE(rec);
            if(type==57u&&RV_WORD(rec+4u)==0x2022a680u)gates|=32u;
        }
        if(!hid&&m!=2u&&m!=3u)gates|=64u;
    }
#ifdef XPAN_D2_DIAG
    if(!xd.xl[0]){
        xd.xl[0]=1u;xd.xl[1]=(uint8_t)gates;xd.xl[2]=(uint8_t)h;
        xd.xl[3]=(uint8_t)type;xd.xl[4]=(uint8_t)hid;xd.xl[6]=(uint8_t)m;
    }
#endif
#else
    /* One redraw of the part-1 type-57 label after the name slot is XPan.
     * Native chain is 0x20319E74 -> 0x203189B4 -> 0x201C0CF4(handle, hide).
     * hide==0 redraws unconditionally. The latch stays shut after one call. */
    uint32_t gates=0,h,type=0xffu,hid=0xffu;
    static const uint8_t name[4]={'X','P','a','n'};
    if(xpan_label_done||RV_WORD(0x205d9c00u)!=5u||!aspect_169())return;
    if(!RV_WORD(0x205d9bf8u))gates|=1u;
    if(session_ok())gates|=2u;
    if(bytes_eq((const volatile uint8_t *)RV_PTR(0x20223150u),name,4u))gates|=4u;
    if(RV_BYTE(0x205a280eu)&1u)gates|=8u;
    if(RV_BYTE(0x205a280fu)==1u)gates|=16u;
    h=RV_BYTE(0x205e4413u);
    if(h>=1u&&h<=RV_BYTE(0x205a27c4u)){
        uint32_t rec=RV_WORD(0x205a27c8u)+8u*(h-1u);
        hid=RV_BYTE(0x205a2416u+h);
        if(rec>=0x20000000u&&rec<=0x207ffff8u&&!(rec&3u)){
            type=RV_BYTE(rec);
            if(type==57u&&RV_WORD(rec+4u)==0x20233a68u)gates|=32u;
        }
        if(!hid)gates|=64u;
    }
#ifdef XPAN_D2_DIAG
    if(!xd.xl[0]){
        xd.xl[0]=1u;xd.xl[1]=(uint8_t)gates;xd.xl[2]=(uint8_t)h;
        xd.xl[3]=(uint8_t)type;xd.xl[4]=(uint8_t)hid;xd.xl[6]=RV_BYTE(0x205df0c8u);
    }
#endif
#endif
    if(gates!=127u)return;
#ifndef ENG_HOST
    /* Same bridge as the baseline #else branch. Target and r4 differ. */
    {
        register uint32_t fn __asm__("r0")=0x201c0cf4u;
        register uint32_t a4 __asm__("r4")=h;
        register uint32_t a5 __asm__("r5")=0u;
        register uint32_t a6 __asm__("r6")=0u;
        __asm__ volatile(
            "push r12\n\t"
            "jl r0\n\t"
            "pop r12\n\t"
            : "+r"(fn), "+r"(a4), "+r"(a5), "+r"(a6)
            :
            : "r1","r2","r3","r7","r8","r9","r10","r11","r13","r14","memory");
    }
#endif
    xpan_label_done=1u;
#ifdef XPAN_D2_DIAG
    /* At most one call per power-on (latch), so this cannot pass 255. */
    ++xd.xl[5];
#endif
#elif !defined(ENG_HOST)
    static uint8_t desc[64];
    static const uint8_t name[4]={'X','P','a','n'};
    const volatile uint8_t *finder;
    uint32_t i,desc_addr;
    status_scene_release();
    if(xpan_status_done)return;
    if(RV_WORD(0x205d9c00u)!=5u||RV_WORD(0x20229350u)!=1u||RV_WORD(0x205d9bf8u))return;
    if(!aspect_169()||!sw_layer1_ok(1)||!session_ok())return;
    finder=RV_PTR(0x20223150u);
    for(i=0;i<4u;++i)if(finder[i]!=name[i])return;
    for(i=0;i<64u;++i)desc[i]=0u;
    desc[34]=1u;desc[36]=1u;
    desc_addr=(uint32_t)desc;
    /* Body jl writes the argument registers and the caller-saved set.
     * r12 stays the PIC register: save and restore it inside the asm,
     * because a clobber of r12 is rejected. The "+r" outputs stop the
     * compiler from reusing r0/r4/r5/r6 for the latch store. */
    {
        register uint32_t fn __asm__("r0")=0x20201e1cu;
        register uint32_t a4 __asm__("r4")=0u;
        register uint32_t a5 __asm__("r5")=desc_addr;
        register uint32_t a6 __asm__("r6")=0u;
        __asm__ volatile(
            "push r12\n\t"
            "jl r0\n\t"
            "pop r12\n\t"
            : "+r"(fn), "+r"(a4), "+r"(a5), "+r"(a6)
            :
            : "r1","r2","r3","r7","r8","r9","r10","r11","r13","r14","memory");
    }
    xpan_status_done=1u;
#endif
}
#ifdef MERGED_R1
int fx_halfpress_hold_view(uint32_t v)
{
    uint32_t p=RV_WORD(0x205d9c04u)&0xffu;
    return v==12u||v==13u||v==14u||v==35u||(v==32u&&(p==13u||p==35u));
}
#endif
static void hw_window_on(void)
{
    uint32_t i;
    if(!subwin_dirty){
        for(i=0;i<5u;++i)saved_subwin[i]=RV_WORD(0x2022936cu+4u*i);
        subwin_dirty=1;
    }
    /* subwindow[0]=0 is the crop. 0x201BEE9C turns it back to 1. */
    RV_WORD(0x2022936cu)=0u;RV_WORD(0x20229370u)=1u;RV_WORD(0x20229374u)=0u;
    RV_WORD(0x20229378u)=122u;RV_WORD(0x2022937cu)=358u;
}
#ifdef XPAN_D123_R1
/* g213 r3 field: the view word leaves 5 on half-press (12,14,13, then 32
 * with previous 13) and the crop is still in place; only our suspend
 * removed it. 35 = released before focus (only native setter 0x202F566C).
 * 0x205D9C04 is the native previous view (0x202B0A74). */
static inline int __attribute__((always_inline)) xpan_hold_view(uint32_t v)
{
#ifdef MERGED_R1
    return fx_halfpress_hold_view(v);
#else
    return v==12u||v==13u||v==14u||v==35u||(v==32u&&(RV_WORD(0x205d9c04u)&0xffu)==13u);
#endif
}
#endif
/* Half-press sets the activity word, then the key handler calls
 * 0x201D9090 -> 0x201BEE9C and the crop disappears. The H51 trampoline
 * at 0x202b1310 runs after that handler, still with activity set.
 * Reapply on that call. The software layer table is a separate gate:
 * the first standby after a new DAT can have the controller ready
 * before the layer words match, and the crop does not need those words. */
void fx_frame_key(uint32_t code)
{
    uint32_t on;
    int quiet,layer_ok,plane_ok;
#ifdef HF6
    int hf_clean;
#endif
    (void)code;
#ifdef XPAN_D123_R1
    {uint32_t view=RV_WORD(0x205d9c00u);
#ifdef XPAN_D2_DIAG
    uint8_t act;
    xd.act='q';
#endif
    if(view!=5u&&!xpan_hold_view(view)){xpan_status_redraw();fx_mask_suspend();return;}
#ifdef XPAN_D2_DIAG
    act=view!=5u?(RV_WORD(0x2022936cu)==0u?'k':'K'):'c';
    xd.act='-';
#endif
#else
    if(RV_WORD(0x205d9c00u)!=5u){xpan_status_redraw();fx_mask_suspend();return;}
#endif
    if(!session_ok()){fx_mask_hw_restore();++fx_image.draw_rejected;return;}
    on=(word(fx_store.header+28)&2u)&&aspect_169();
    if(!on&&!mask_active&&!subwin_dirty&&!clut_dirty_mask&&!scan_dirty){xpan_status_redraw();return;}
#ifdef HF6
    hf_clean=on?hf1_release_for_xpan():1;
#endif
    /* Activity during standby is half-press. The legacy cases require the
     * software plane to stay unchanged while that word is set. The hardware
     * crop is still reapplied, because 0x201BEE9C has just turned it off. */
#ifdef XPAN_D123_R1
    quiet=view==5u&&!RV_WORD(0x205d9bf8u);
#else
    quiet=!RV_WORD(0x205d9bf8u);
#endif
    layer_ok=sw_layer1_ok(1);
    /* Installed table, one pointer off: the legacy check rejects the draw.
     * An empty table on the first standby is not that case, and the crop
     * below does not need the three layer words. */
    if(!layer_ok&&RV_WORD(0x205a1594u)==1u&&(RV_BYTE(0x205a280eu)&1u)&&
       RV_WORD(0x205a19a4u)==0x20744800u&&RV_WORD(0x200c0dc8u)==0x20744800u){
        fx_mask_hw_restore();
        ++fx_image.draw_rejected;
        return;
    }
    if(layer_ok&&quiet)sw_bars_apply((int)on);
    if(on){
        if(layer_ok)mask_active|=1u;
        plane_ok=RV_WORD(0x200c0dc8u)==0x20744800u&&RV_WORD(0x200c0dccu)==0x177800u;
        if(is_xpan_unit()){
            /* First standby after a new DAT reaches BOOT_RUN while
             * 0x20229350 is still 0 and the layer table is empty. The crop
             * words are ordinary RAM. CLUT MMIO stays behind the ready bit. */
#ifdef HF6
            if(RV_WORD(0x20229350u)==1u){
                if(hf_clean&&clut_apply_on()){
                    hw_window_on();
                    hw_bars_scan_on();
                    mask_active|=2u;
                }
            }else if(hf_clean&&plane_ok){
                hw_window_on();
                mask_active|=2u;
            }
#else
            if(RV_WORD(0x20229350u)==1u&&clut_apply_on()){
                hw_window_on();
                hw_bars_scan_on();
                mask_active|=2u;
            }else if(plane_ok){
                hw_window_on();
                mask_active|=2u;
            }
#endif
        }else{
            fx_mask_hw_restore();
        }
        ++fx_image.drawn;
        if(quiet&&layer_ok)xpan_status_redraw();
    }else{
        xpan_status_redraw();
        fx_mask_hw_restore();
        mask_active&=~1u;
    }
#ifdef XPAN_D123_R1
#ifdef XPAN_D2_DIAG
    xd.act=act;
#endif
    }
#endif
}
int32_t fx_image_entry(const RvRequest *q,RvReply *r)
{
    (void)r;
    if(q->args[8]==40)++fx_image.h40;
    if(q->args[8]==41)++fx_image.h41;
    return RV_PASS;
}
#ifdef HF1
int fx_session_ok(void){return session_ok();}
int fx_aspect_169(void){return aspect_169();}
int fx_sw_layer1_ok(int require_visible){return sw_layer1_ok(require_visible);}
int fx_hw_scan_ok(void){return hw_scan_ok();}
#if defined(HF1_DIAG) || defined(HF4)
uint8_t fx_aspect_byte(void)
{
    uint32_t s=RV_WORD(0x200c0dac),n=RV_WORD(0x200c0db0),off;
    if(s<0x20000000u||s>0x207ff000u||n!=0x1000u)return 0xffu;
    off=RV_BYTE(0x205d9a7f)==2?0xa89u:0x3f4u;
    return RV_BYTE(s+off);
}
#endif
#ifdef HF5
static const uint8_t  hf_clut_idx[4] = {254u, 220u, 221u, 222u};
/* = cold-palette values of 206, 203, 204, 205 (root checked 08:40Z:
 * 0x08008080, 0x04C78080, 0x08FE8080, 0x08008080); 254/220-222 are
 * 0x04358080 (half-transparent grey) at cold start. */
static const uint32_t hf_clut_on[4]  = {0x08008080u, 0x04C78080u, 0x08FE8080u, 0x08008080u};
static uint32_t hf_saved_subwin[5], hf_saved_clut[4];
static uint8_t  hf_subwin_dirty, hf_clut_dirty;

#ifdef HF6
int fx_hf_hw_clean(void)
{
    return hf_subwin_dirty == 0u && hf_clut_dirty == 0u;
}
#endif

void fx_hf_hw_release(void)
{
    volatile uint32_t *sw = (volatile uint32_t *)RV_PTR(0x2022936cu);
    volatile uint32_t *clut = (volatile uint32_t *)RV_PTR(0xf0218000u);
    uint32_t i, y, x;
#ifndef ENG_HOST
    __asm__("" : "+r"(sw));
#endif
    if (hf_subwin_dirty) {
        for (i = 0u; i < 5u; ++i) sw[i] = hf_saved_subwin[i];
        hf_subwin_dirty = 0u;
        if (hw_scan_ok()) {
            for (y = 28u; y < 452u; ++y) {
                volatile uint8_t *row = RV_PTR(0x20744800u + y * 640u);
                for (x = 0u; x < 640u; ++x) {
                    uint8_t v;
#ifdef HF10_SEAM25
                    if (x == 168u) x = 472u;   /* 250: same columns as the layer-1 bars */
#else
                    if (x == 160u) x = 480u;
#endif
                    v = row[x];
                    if (v == 254u) row[x] = 0u;
                    else if (v == 220u) row[x] = 182u;
                    else if (v == 221u) row[x] = 183u;
                    else if (v == 222u) row[x] = 200u;
                }
            }
        }
    }
    if (hf_clut_dirty) {
        for (i = 0u; i < 4u; ++i) {
            if (!(hf_clut_dirty & (1u << i))) continue;
            if (!clut_wait_ready()) break;
            clut[hf_clut_idx[i]] = hf_saved_clut[i];
            hf_clut_dirty &= (uint8_t)~(1u << i);
        }
    }
}

uint32_t fx_hf_hw_hold(void)
{
#ifdef HF10_SEAM25
    static const uint16_t want[5] = {0u, 0u, 0u, 168u, 472u};   /* 250: = layer-1 bars */
#else
    static const uint16_t want[5] = {0u, 0u, 0u, 160u, 480u};
#endif
    volatile uint32_t *mm = (volatile uint32_t *)RV_PTR(0x20229350u);
    volatile uint32_t *sw;
    volatile uint32_t *clut = (volatile uint32_t *)RV_PTR(0xf0218000u);
    uint32_t bits = 0u, i;
    int diff = 0;
#ifndef ENG_HOST
    __asm__("" : "+r"(mm));
#endif
    sw = mm + 7;
    if (mm[5] == 0u) bits |= 1u;
    if (mm[6] == 1u) bits |= 2u;
    if (mm[0] == 1u) bits |= 4u;
    if (hw_scan_ok()) bits |= 16u;
    if (session_ok()) bits |= 32u;
    if (subwin_dirty || clut_dirty_mask || scan_dirty) return bits;
    if (!is_xpan_unit() || (bits & 0x17u) != 0x17u) {
        fx_hf_hw_release();
        return bits;
    }
    for (i = 0u; i < 4u; ++i) {
        uint32_t idx = hf_clut_idx[i];
        if (!clut_wait_ready()) {
            fx_hf_hw_release();
            return bits;
        }
        if (!(hf_clut_dirty & (1u << i))) {
            hf_saved_clut[i] = clut[idx];
            hf_clut_dirty |= (uint8_t)(1u << i);
        }
        clut[idx] = hf_clut_on[i];
    }
    bits |= 8u;
    if (hf_subwin_dirty && sw[0] != 0u) bits |= 64u;
    for (i = 0u; i < 5u; ++i) {
        if (sw[i] != want[i]) {
            diff = 1;
            break;
        }
    }
    if (diff) {
        for (i = 0u; i < 5u; ++i) {
            if (!hf_subwin_dirty) hf_saved_subwin[i] = sw[i];
            sw[i] = want[i];
        }
        hf_subwin_dirty = 1u;
        bits |= 128u;
    }
    return bits;
}
#endif
#endif
#ifdef L2N_FOLD_A
#include "l2n_fold.inc.c"
#endif
