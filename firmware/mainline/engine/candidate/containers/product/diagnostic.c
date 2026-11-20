#ifndef G175_DIAG_SILENT
#define G175_DIAG_SILENT 2
#endif
#include "diagnostic.h"
#include "src/firmware/card_container_v2/internal.h"
static uint32_t get32(const uint8_t *p){return (uint32_t)p[0]<<24|(uint32_t)p[1]<<16|(uint32_t)p[2]<<8|p[3];}
static uint32_t crc(const uint8_t *p,unsigned n){return gxr2_crc32(p,n);}
static int card(uint32_t id[4]){return !rv_native_sd_id(id)&&(id[0]|id[1]|id[2]|id[3]);}
int ig_control_off(void)
{
    uint32_t before[4],after[4];uint8_t raw[16],extra;unsigned at=0;int32_t fd,n,closed;int ok=1;
    if(!card(before))return 0;
    fd=rv_native_open("/ATA1/GXRCE.CTL",0);if(fd<0)return 0;
    while(at<16){n=rv_native_read(fd,raw+at,16-at);if(n<=0||(unsigned)n>16-at){ok=0;break;}at+=(unsigned)n;}
    n=rv_native_read(fd,&extra,1);closed=rv_native_close(fd);
    return ok&&n==0&&!closed&&card(after)&&pn_equal(before,after,16)&&
        pn_equal(raw,"GXRC3401",8)&&get32(raw+8)==0&&crc(raw,12)==get32(raw+12);
}

static const RvPrivateContext *dc;
static BootDiagnostic *d;
void diag_init(const RvPrivateContext *c)
{
    dc=c;d=eng_wire_pointer(c->state_address+DIAG_ENGINE_BYTES);
    pn_zero(d,sizeof(*d));d->magic=0x47313537;
}
void diag_capture(unsigned entry)
{
    RvRoot *r=RV_PTR(dc->root_address);RvSession *s=RV_PTR(dc->session_address);
    if(d->entry)return;
    d->entry=(uint8_t)entry;d->phase=1;
    d->settings=RV_WORD(0x200c0dac);d->length=RV_WORD(0x200c0db0);
    d->mode=RV_BYTE(0x205d9a7f);d->submode=RV_BYTE(0x205d9a9f);
    d->my=RV_BYTE(0x205d9aa3);d->pending=RV_BYTE(0x205da00b);
    d->activity=RV_WORD(0x205d9bf8);d->state=RV_WORD(0x205d9c00);
    d->boot_word=r->reserved_lane;d->root_flags=r->flags;d->resident=r->state;
    d->source=(uint8_t)s->selected_source;d->settings_epoch=r->epoch[RV_S_E];
    d->first_failure=r->check_failure;
    if(entry==51)d->seen=7; /* H50 inferred from pending; H51 and DAT entry observed. */
    if(d->settings>=0x20000000u&&d->settings<=0x207ff000u&&d->length==0x1000){
        d->selection=RV_WORD(d->settings+0x2fc);d->selector=RV_BYTE(d->settings+0x36e);
        d->wb[0]=RV_BYTE(d->settings+0x6dd);d->wb[1]=RV_BYTE(d->settings+0x6de);
    }
}
void diag_reason(unsigned reason,uint32_t bits)
{ d->failed|=bits;if(!d->reason){d->reason=(uint8_t)reason;d->record=(uint8_t)eng_memory_result();} }
void diag_engine(unsigned stage){d->seen|=8;d->stage=(uint8_t)stage;}
unsigned diag_page(void)
{
    if(!d->entry){diag_capture(1);diag_reason(1,BF_DISPATCH);}
    /* r3: normal paths open no page. reason 1 (B01: H51 did not reach the
     * DAT, the first ADJ loaded it) and reason 2 (B02: release, BOOT off by
     * design; boot_run forces reason 2 whatever eligibility bits ride along,
     * e.g. no saved record) stay recorded for diag_code and the Status row.
     * Reasons 10 and above come only from the test BOOT path or a real
     * in-transaction fault, and open the page once. Superset of the
     * g162-on-r2 rule, which silenced BF_DISPATCH alone. */
    /* r4/g172: BOOT runs in both profiles. Reasons up to G175_DIAG_SILENT
     * stay recorded for diag_code and the Status row but open no page:
     * release 21 (B10-B21 are eligibility skips such as no saved record,
     * non-Standard image setting or MY; only transaction faults B22+ open
     * it), test 2 (as g168 test: every BOOT reason opens it once). */
    if(d->shown||d->reason<=G175_DIAG_SILENT)return 0;
    d->shown=1;return 1;
}
unsigned diag_code(void){return d->reason;}
#ifdef HF1_DIAG
void hf1_diag_line(unsigned row,char out[14]);
#if defined(HF9_DIAG)
/* 247: [Z z] A a h k v [y] H R P Q [X] (DIAG_ROWS in diagnostic.h); v replaces x */
void l2n_fold_diag_line(unsigned row,char out[14]);
void hf7_diag_line(unsigned row,char out[14]);
void hf8_diag_line(unsigned row,char out[14]);
#define L2N_DIAG_SKIP (HF9_DIAG_TRIM>=1?2u:0u)
#define HF8_DIAG_N (HF9_DIAG_TRIM>=3?1u:2u)
void __attribute__((noinline)) diag_text(unsigned row,char out[14])
{row+=L2N_DIAG_SKIP;if(row<4)l2n_fold_diag_line(row,out);else if(row<6)hf7_diag_line(row-4,out);else if(row<6+HF8_DIAG_N)hf8_diag_line(row-6,out);else hf1_diag_line(row-6-HF8_DIAG_N,out);}
#elif defined(HF8_DIAG)
void l2n_fold_diag_line(unsigned row,char out[14]);
void hf7_diag_line(unsigned row,char out[14]);
void hf8_diag_line(unsigned row,char out[14]);
#ifdef XPAN_ZOOM_R2
#define L2N_DIAG_SKIP 0u /* Z z A a */
#else
#define L2N_DIAG_SKIP 2u /* A a */
#endif
void __attribute__((noinline)) diag_text(unsigned row,char out[14])
{row+=L2N_DIAG_SKIP;if(row<4)l2n_fold_diag_line(row,out);else if(row<6)hf7_diag_line(row-4,out);else if(row<8)hf8_diag_line(row-6,out);else hf1_diag_line(row-8,out);}
#elif defined(XPAN_ZOOM_R1) && defined(HF7_H43)
void l2n_fold_diag_line(unsigned row,char out[14]);
void hf7_diag_line(unsigned row,char out[14]);
void __attribute__((noinline)) diag_text(unsigned row,char out[14])
{if(row<4)l2n_fold_diag_line(row,out);else if(row<6)hf7_diag_line(row-4,out);else hf1_diag_line(row-6,out);}
#else
void __attribute__((noinline)) diag_text(unsigned row,char out[14]){hf1_diag_line(row,out);}
#endif
#elif defined(XPAN_D2_DIAG)
void xd_line(unsigned row,char out[14]);
void __attribute__((noinline)) diag_text(unsigned row,char out[14]){xd_line(row,out);}
#else
static void hex(char *p,uint32_t value,unsigned n)
{static const char digits[]="0123456789ABCDEF";while(n){p[--n]=digits[value&15];value>>=4;}}
typedef struct {uint8_t row,offset,column,width;} DiagField;
#define DF(r,f,c,w,b) {r,offsetof(BootDiagnostic,f),c,w}
static const DiagField fields[]={
 DF(1,failed,1,8,4),DF(4,record,12,1,1),
 DF(2,mode,1,2,1),DF(2,submode,4,2,1),DF(2,my,7,2,1),DF(2,pending,10,2,1),
 DF(3,activity,1,8,4),DF(3,seen,10,2,1),DF(4,state,1,8,4),DF(4,stage,10,1,1),
 DF(5,selection,1,8,4),DF(5,source,10,2,1),DF(6,settings,1,8,4),DF(6,length,9,4,4),
 DF(7,selector,1,2,1),DF(7,wb[0],3,2,1),DF(7,wb[1],5,2,1),DF(7,resident,8,1,1)};
void __attribute__((noinline)) diag_text(unsigned row,char out[14])
{
    static const char lines[8][14]={"G175B00R00","F00000000A--","M00U00Y00P00","A00000000H00",
        "V00000000T0R0","N00000000L00","S000000000000","I000000Q0D0G0"};
    const uint8_t *bytes=(const uint8_t *)d;unsigned i;
#if defined(ONE_STEP_ZOOM) && !defined(OZ_NO_DIAG)
    /* Z rr:nn fsc gg = rewrites, 0x5D seen in view 5, then at the last 0x5D
     * the low digits of 0x2037F883, the word, capability 43, gate bits. */
    if(row==8){const uint8_t *o=oz_diag;pn_copy(out,"Z00:00 000 00",14);
        hex(out+1,o[0],2);hex(out+4,o[1],2);hex(out+7,o[2],1);hex(out+8,o[3],1);hex(out+9,o[4],1);hex(out+11,o[5],2);return;}
#endif
#ifdef HF_ALL_UNITS
    /* U tt e RR (5 hex digits, no spaces): see hfu_diag (hf1.c) */
#ifdef OZ_NO_DIAG
    if(row==8){out[0]='U';out[6]=0;hex(out+1,hfu_diag(),5);return;} /* 256: Z dropped, U is row 8 */
#else
    if(row==9){out[0]='U';out[6]=0;hex(out+1,hfu_diag(),5);return;}
#endif
#endif
    pn_copy(out,lines[row],14);
    for(i=0;i<sizeof(fields)/sizeof(fields[0]);++i){const DiagField *f=&fields[i];
        if(f->row==row){
            if(d->entry!=51&&row>=2&&row<=5)pn_copy(out+f->column,"????????",f->width);
            else hex(out+f->column,f->width>2?*(const uint32_t *)(const void *)(bytes+f->offset):bytes[f->offset],f->width);
        }
    }
    if(!row){
        out[5]='0'+d->reason/10;out[6]='0'+d->reason%10;hex(out+8,eng_saved_code(),2);
    }else if(row==1){unsigned active=eng_active_code();
        if(!active&&eng_baseline())active=4;
        if(active)hex(out+10,active,2);
    }
    if(row==7){out[10]='0'+!!(d->boot_word&4);out[12]='0'+!!(d->boot_word&8);}
}
#endif
