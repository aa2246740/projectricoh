#include "eng_entries.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define BASE UINT32_C(0x20120000)
#define MEM_BYTES 131072u
static uint8_t image[49152],original[49152]; static uint32_t image_bytes;
static uint16_t b16(const uint8_t *p) { return (uint16_t)((unsigned)p[0]*256u+p[1]); }
static uint32_t b32(const uint8_t *p) { return (uint32_t)b16(p)*65536u+b16(p+2); }
static const void *addresses[4096]; static unsigned address_count;
uint32_t eng_wire_address(const void *p)
{
    unsigned i; if(!p) return 0;
    for(i=0;i<address_count;i++) if(addresses[i]==p) return 0x1000u+4*i;
    assert(address_count<4096); addresses[address_count++]=p; return 0x1000u+4*(address_count-1);
}
void *eng_wire_pointer(uint32_t a)
{
    if(!a) return 0; assert(a>=0x1000 && !(a&3) && (a-0x1000)/4<address_count);
    return (void *)addresses[(a-0x1000)/4];
}
typedef struct {
    uint8_t memory[MEM_BYTES],settings[4096],ui[2048]; EngGrain grain;
    uint32_t epochs[12],cursor,page; unsigned unit,t,begin,ends,held,w,v,x,snapshots,patch,preview,releases;
    unsigned core_reenter,native_reenter,fail_w,fail_v,fail_x,fail_patch,fail_preview,fail_release,fail_end,epoch_w,short_settings;
    unsigned writes[8],t_values[128],t_writes;
    unsigned trace[1024],tracen,trace_enabled,ui_binds,ui_releases,texts,last_ui_cursor,ui_cursor_calls;
} Fake;
static Fake f;
static unsigned bad_pin;
uint32_t rv_unit_pin(uint8_t unit)
{ static const uint32_t pins[3]={0xdf2bcaf5,0x6700e6ff,0x1b3c7000}; return unit<3?(pins[unit]^((bad_pin && unit==f.unit)?1u:0u)):0; }
static EngData data;
static Gxr2View gated;
static Gxr2Trust host_trust;
static uint32_t row_addr(unsigned row) { return b32(data.map+32+12*row); }
static uint16_t read_word(uint32_t a)
{
    assert(a>=BASE && a-BASE<MEM_BYTES-1); return b16(f.memory+(a-BASE));
}
static void write_word(uint32_t a,unsigned v)
{
    assert(a>=BASE && a-BASE<MEM_BYTES-1); f.memory[a-BASE]=(uint8_t)(v>>8); f.memory[a-BASE+1]=(uint8_t)v;
}
static int32_t mock(void *user,uint32_t sid,uint32_t op,uint32_t a,uint32_t b,void *p,uint32_t bytes,uint32_t count,RvReply *r)
{
    unsigned i; int32_t status=RV_OK; (void)user;(void)b;(void)count;
    memset(r,0,sizeof(*r));r->version=1;r->bytes=sizeof(*r);
    if(sid==RV_EPOCHS) {
        RvEpochSnapshot *s=p; assert(op==12 && bytes==sizeof(*s));
        s->session_token=17;memcpy(s->epochs,f.epochs,sizeof(f.epochs));
    } else if(sid==RV_UNIT) {
        RvUnitInfo *u=p;static const uint8_t names[3][8]={"jlaunch","qlaunch","l08firm"};
        assert(op==1 && bytes==sizeof(*u));memcpy(u->name,names[f.unit],8);u->main_version=0x151;u->cmp_version=0;
        u->unit_epoch=f.epochs[RV_UNIT_E];u->link_epoch=f.epochs[RV_LINK_E];u->rx_sequence=19;u->valid=1;
    } else if(sid==RV_RPC8) {
        if(op==1) { assert(!f.held);f.held=1;f.begin++;r->token=7; }
        else if(op==5) { assert(f.held);f.held=0;f.ends++;if(f.fail_end && f.ends==f.fail_end)status=RV_IO; }
        else {
            assert(f.held && a<=65535);
            if(op==4) {
                if(f.core_reenter) {
                    EngRecipeRef rr;EngTweak tt={{0}};f.core_reenter=0;
                    rr.unit=(uint8_t)f.unit;rr.slot=1;eng_identity(eng_record(&data,1),rr.identity);
                    assert(eng_apply(&rr,&tt)==ENG_REJECTED);
                }
                f.x++;f.page=a;r->native_result=(int32_t)a;if(f.fail_x && f.x==f.fail_x)status=RV_IO; }
            else if(op==2) {
                f.v++;
                if(f.page==0x12c0) { assert(a==0x2444);f.cursor=0;r->native_result=(int32_t)f.t; }
                else { f.cursor=(f.page<<16)|(a&65534);r->native_result=read_word(f.cursor); }
                if(f.fail_v && f.v==f.fail_v)status=RV_IO;
            } else {
                assert(op==3 && eng_uncertain() && !f.grain.armed); f.w++;
                if(f.page==0x12c0) {
                    assert(f.cursor==0);f.t=a;
                    assert(f.t_writes<128);f.t_values[f.t_writes++]=a;
                    if(f.trace_enabled)f.trace[f.tracen++]=7;
                } else {
                    unsigned found=8;
                    for(i=0;i<7;i++) if(f.cursor>=((row_addr(i))&~1u) && f.cursor<=row_addr(i)+b16(data.map+32+12*i+4)-1) {found=i;break;}
                    assert(found<7 && f.t==2);f.writes[found]++;if(f.trace_enabled)f.trace[f.tracen++]=found;
                    write_word(f.cursor,a);
                }
                f.cursor+=2;r->native_result=(int32_t)a;
                if(f.epoch_w && f.w==f.epoch_w) f.epochs[RV_LINK_E]++;
                if(f.fail_w && f.w==f.fail_w) status=RV_IO;
            }
        }
    } else if(sid==RV_SETTINGS) {
        if(op==1) {
            RvSettingsInfo *s=p;assert(bytes==sizeof(*s));f.snapshots++;
            s->token=29;s->address=eng_wire_address(f.settings);s->length=f.short_settings?10:sizeof(f.settings);s->settings_epoch=f.epochs[RV_S_E];
        } else if(op==2) {
            RvSettingsPlan *s=p;assert(bytes==sizeof(*s) && s->count<=16 && s->settings_token==29 && !f.grain.armed);
            f.patch++;
            for(i=0;i<s->count;i++) { assert(s->writes[i].offset<4096);f.settings[s->writes[i].offset]=s->writes[i].value; }
            if(f.fail_patch)status=RV_IO;
        } else {assert(op==3 && a==29);f.releases++;if(f.fail_release && f.releases==f.fail_release) status=RV_IO;}
    } else if(sid==RV_PREVIEW) {assert(op==1);f.preview++;if(f.fail_preview)status=RV_IO;}
    else if(sid==RV_LEASE) {
        RvLeaseInfo *l=p;assert(op==1 && a<=sizeof(f.ui));l->base=eng_wire_address(f.ui);l->length=sizeof(f.ui);l->token=61;
    } else if(sid==RV_UI_TEXT) {
        if(op==1) {RvUiText *t=p;assert(t->glyph_capacity==96 && t->source_bytes<=32);f.texts++;memcpy(eng_wire_pointer(t->glyph_address),eng_wire_pointer(t->source_address),t->source_bytes);t->actual_bytes=t->source_bytes+1;}
        else {assert(op==2);r->detail=1;}
    } else if(sid==RV_UI_LIST) {
        if(op==1) {RvUiList *l=p;assert(l->rows==16 && l->lease_token==61);f.ui_binds++;r->token=71;}
        else if(op==4)f.ui_releases++;
        else if(op==2){RvUiList *l=p;assert(l->rows==16 && l->view_token==71);f.last_ui_cursor=l->cursor;f.ui_cursor_calls++;((uint8_t *)eng_wire_pointer(l->state_address))[10]=(uint8_t)l->cursor;}
        else assert(op==3);
    } else assert(0);
    r->status=status;return status;
}
static EngPort port(void)
{
    EngPort p; unsigned i;memset(&p,0,sizeof(p));p.call=mock;p.grain=&f.grain;p.gated=&gated;
    for(i=0;i<3;i++) {p.wb[i].valid=1;p.wb[i].lane=0;p.wb[i].ab_sign=1;p.wb[i].gm_sign=-1;}
    return p;
}
static void p32(uint8_t *p,uint32_t x)
{p[0]=(uint8_t)(x>>24);p[1]=(uint8_t)(x>>16);p[2]=(uint8_t)(x>>8);p[3]=(uint8_t)x;}
static void reseal(void)
{p32(image+24,eng_crc(image+256,image_bytes-256));p32(image+20,0);p32(image+20,eng_crc(image,256));}
static EngStatus validate_pipeline(const uint8_t *p,uint32_t n,const RvUnitInfo *u,EngData *out)
{
    Gxr2Unit unit;Gxr2View v;memcpy(unit.name,u->name,8);unit.main_version=u->main_version;unit.cmp_version=u->cmp_version;
    if(gxr2_gate_validate(p,n,&host_trust,&unit,0,&v)!=GXR2_OK || eng_data_accept(&v)!=ENG_OK)return ENG_REJECTED;
    return eng_data_validate(p,n,u,out);
}
static void make_gate(void)
{
    RvUnitInfo u;RvReply reply;Gxr2Unit unit;
    memset(&u,0,sizeof(u));u.header.version=1;u.header.bytes=sizeof(u);mock(0,RV_UNIT,1,0,0,&u,sizeof(u),0,&reply);
    memcpy(unit.name,u.name,8);unit.main_version=u.main_version;unit.cmp_version=u.cmp_version;
    assert(gxr2_gate_validate(image,image_bytes,&host_trust,&unit,0,&gated)==GXR2_OK);
    assert(eng_data_accept(&gated)==ENG_OK);
}
static void setup(unsigned unit)
{
    RvUnitInfo u;unsigned i;memset(&f,0,sizeof(f));f.unit=unit;f.t=2;
    for(i=0;i<12;i++)f.epochs[i]=1;
    memset(&u,0,sizeof(u));u.header.version=1;u.header.bytes=sizeof(u);
    {RvReply r;mock(0,RV_UNIT,1,0,0,&u,sizeof(u),0,&r);}
    make_gate();assert(eng_data_validate(image,image_bytes,&u,&data)==ENG_OK);
    for(i=0;i<7;i++)memcpy(f.memory+(row_addr(i)-BASE),eng_entry(&data,0)+b16(data.map+32+12*i+6),b16(data.map+32+12*i+4));
    f.memory[row_addr(1)+33-BASE]=0xa7;f.memory[row_addr(5)-1-BASE]=0x5c;f.memory[row_addr(5)+33-BASE]=0xd3;
    f.settings[0x3aa]=1;f.settings[0xc9d]=3;
}
static void init(void) {EngPort p;reseal();make_gate();p=port();assert(eng_init(image,image_bytes,&p)==ENG_OK);assert(!f.w && !f.patch && !f.preview);}
static EngRecipeRef ref(unsigned slot)
{EngRecipeRef r;r.unit=(uint8_t)f.unit;r.slot=(uint8_t)slot;eng_identity(eng_record(&data,slot),r.identity);return r;}
static void verify_neighbors(void)
{assert(f.memory[row_addr(1)+33-BASE]==0xa7);assert(f.memory[row_addr(5)-1-BASE]==0x5c);assert(f.memory[row_addr(5)+33-BASE]==0xd3);}
static void verify_stock(void)
{
    unsigned i;assert(f.t==2);
    for(i=0;i<7;i++)assert(!memcmp(f.memory+(row_addr(i)-BASE),eng_entry(&data,0)+b16(data.map+32+12*i+6),b16(data.map+32+12*i+4)));
    verify_neighbors();
}
static void slots(void)
{
    unsigned slot;EngRecipeRef r;EngTweak t;
    init();assert(eng_current(&r,&t)==ENG_STALE);assert(eng_menu_open()==ENG_OK);
    for(slot=1;slot<=16;slot++) {
        assert(eng_list()->row[slot-1].occupied);assert(eng_select((uint8_t)slot)==ENG_OK);
        assert(eng_current(&r,&t)==ENG_OK && r.slot==slot && r.unit==f.unit);verify_neighbors();
        assert(f.settings[0x36e]==r.identity[33]);
        if(slot==6) {unsigned w=f.w;eng_menu_close();assert(eng_menu_open()==ENG_OK);assert(f.w==w && f.t==0);}
    }
    assert(eng_select(4)==ENG_OK);verify_stock();
    printf("slots: unit=%u, all 16 slots, stock restore, neighbors, reopen T0\n",f.unit);
}
static void tweaks(void)
{
    EngRecipeRef r;EngTweak t={{0}},out;unsigned i,w;int c,h,s;
    init();r=ref(1);assert(eng_apply(&r,&t)==ENG_OK);
    w=f.w;t.v[0]=1;memset(f.writes,0,sizeof(f.writes));assert(eng_apply(&r,&t)==ENG_OK);
    assert(f.w-w==17 && f.writes[1]==17);for(i=0;i<7;i++)if(i!=1)assert(!f.writes[i]);
    w=f.w;t.v[4]=2;t.v[5]=-3;assert(eng_apply(&r,&t)==ENG_OK);assert(f.w==w);
    assert(f.settings[0x6dd]==11 && f.settings[0x6de]==12);
    for(c=-8;c<=8;c+=4)for(h=-8;h<=8;h+=4)for(s=-8;s<=8;s+=4) {
        t.v[0]=(int8_t)c;t.v[1]=(int8_t)h;t.v[2]=(int8_t)s;t.v[3]=(int8_t)(-s);
        assert(eng_apply(&r,&t)==ENG_OK);assert(eng_current(&r,&out)==ENG_OK && !memcmp(&t,&out,sizeof(t)));verify_neighbors();
    }
    memset(&t,0,sizeof(t));assert(eng_apply(&r,&t)==ENG_OK);
    assert(!memcmp(f.memory+(row_addr(1)-BASE),eng_entry(&data,eng_meta_record(&data,1)[24])+82,33));
    printf("tweaks: unit=%u, 125 extreme combinations, tone=17 W, WB=0 W, recompute default\n",f.unit);
}
static void failure(const char *kind,unsigned at)
{
    EngRecipeRef r,old;EngTweak t={{0}},read;unsigned w,patches,previews;
    init();assert(eng_menu_open()==ENG_OK);assert(eng_select(4)==ENG_OK);r=ref(6);t.v[4]=1;patches=f.patch;previews=f.preview;
    if(!strcmp(kind,"failw")) f.fail_w=f.w+at;
    else if(!strcmp(kind,"failx"))f.fail_x=f.x+at;
    else if(!strcmp(kind,"failv"))f.fail_v=f.v+at;
    else if(!strcmp(kind,"epoch"))f.epoch_w=f.w+at;
    else if(!strcmp(kind,"patch"))f.fail_patch=1;
    else if(!strcmp(kind,"preview"))f.fail_preview=1;
    else if(!strcmp(kind,"release"))f.fail_release=f.releases+1;
    else if(!strcmp(kind,"end"))f.fail_end=f.ends+1;
    else assert(0);
    assert(eng_apply(&r,&t)!=ENG_OK);assert(!f.grain.armed);
    if(eng_uncertain()) {
        w=f.w;eng_menu_close();assert(eng_menu_open()!=ENG_OK);eng_invalidate();assert(eng_rebind()==ENG_UNCERTAIN);
        assert(eng_apply(&r,&t)==ENG_UNCERTAIN && f.w==w);assert(eng_current(&old,&read)==ENG_UNCERTAIN);
    } else {
        assert(f.patch==patches && f.preview==previews);
        assert(eng_current(&old,&read)==ENG_OK && old.slot==4);
    }
    assert(!f.held);verify_neighbors();
    printf("failure: unit=%u %s/%u, W=%u, uncertain=%d, stage=%u\n",f.unit,kind,at,f.w,eng_uncertain(),eng_stage());
}
static void t1(void)
{
    unsigned i,last=0;init();assert(eng_menu_open()==ENG_OK);assert(eng_select(6)==ENG_OK && f.t==0);
    memset(f.writes,0,sizeof(f.writes));f.tracen=f.t_writes=0;f.trace_enabled=1;
    assert(eng_select(7)==ENG_OK && f.t==0);
    assert(f.t_writes==2 && f.t_values[0]==2 && f.t_values[1]==0);
    assert(f.trace[0]==7 && f.trace[f.tracen-1]==7);
    for(i=1;i+1<f.tracen;i++){assert(f.trace[i]>=last && f.trace[i]<7);last=f.trace[i];}
    assert(eng_select(4)==ENG_OK);verify_stock();
    printf("T1: unit=%u, disable-before-rows, enable-last, C/D only at T2\n",f.unit);
}
static void startup_test(const char *kind)
{
    EngPort p=port(); unsigned w;
    if(!strcmp(kind,"startup"))f.t=0;
    else if(!strcmp(kind,"startup-fail"))f.fail_x=1;
    else if(!strcmp(kind,"startup-write-fail")){f.t=0;f.fail_w=1;}
    assert(eng_init(image,image_bytes,&p)==ENG_OK);assert(!f.w && !f.patch && !f.preview);
    if(!strcmp(kind,"startup-write-fail"))assert(eng_menu_open()==ENG_UNCERTAIN);
    else {
        assert(eng_menu_open()==ENG_OK && f.t==2);
        assert(eng_list()->warning==(!strcmp(kind,"startup")));
        if(eng_list()->warning)assert(!strncmp(eng_list()->row[3].ascii,"!4",2));
        w=f.w;eng_menu_close();assert(eng_menu_open()==ENG_OK && f.w==w);
    }
    printf("startup: unit=%u %s, pure init W=0, menu W=%u\n",f.unit,kind,f.w);
}
static void grain(void)
{
    uint8_t p[144],before[144];EngEpoch e={1,1,1,1,1,1,1};unsigned i,category,size;
    static const unsigned fields[]={0x1a,0x14,0x75,0x1e,0x26};
    init();assert(eng_menu_open()==ENG_OK);assert(eng_select(3)==ENG_OK && f.grain.armed);
    memset(before,0,sizeof(before));before[0x0f]=7;before[0x33]=3;before[0x34]=5;before[0x35]=8;before[0x36]=1;
    for(category=0;category<6;category++)for(size=0;size<20;size++) {
        int wanted=(category==0 || category==4) && (size==1 || size==2 || size==5 || size==8 || size==12 || size==16);
        f.settings[0x3aa]=(uint8_t)size;memcpy(p,before,sizeof(p));
        assert(eng_grain_gate(&f.grain,&e,category,f.settings,sizeof(f.settings),p,sizeof(p))==wanted);
        if(wanted){assert(p[0x1a]==21 && p[0x10]==0 && p[0x32]==1 && p[0x6f]==3);p[0x1a]=0;p[0x32]=0;p[0x6f]=0;}
        assert(!memcmp(p,before,sizeof(p)));
    }
    f.settings[0x3aa]=1;
    for(i=0;i<5;i++){memcpy(p,before,sizeof(p));p[fields[i]]=1;memcpy(before,p,sizeof(p));assert(!eng_grain_gate(&f.grain,&e,0,f.settings,4096,p,144));assert(!memcmp(p,before,144));before[fields[i]]=0;}
    memcpy(p,before,144);e.link++;assert(!eng_grain_gate(&f.grain,&e,0,f.settings,4096,p,144));e.link--;
    assert(!eng_grain_gate(&f.grain,&e,0,f.settings,0xc9d,p,144));
    f.settings[0x36e]^=1;assert(!eng_grain_gate(&f.grain,&e,0,f.settings,4096,p,144));
    assert(!memcmp(p,before,144));eng_invalidate();assert(!f.grain.armed);
    printf("grain: unit=%u, 120 category/size gates, five packet gates, epochs, S length/selector\n",f.unit);
}
static void golden(void)
{
    uint8_t block[420]; FILE *in=fopen(getenv("ENG_CORE_GOLDEN"),"rb"); unsigned count=0,i,pos;
    assert(in);init();
    while(fread(block,1,sizeof(block),in)==sizeof(block)) {
        EngRecipeRef r;EngTweak t;
        if(block[0]!=f.unit) continue;
        r=ref(block[1]);for(i=0;i<8;i++)t.v[i]=(int8_t)block[2+i];
        assert(eng_apply(&r,&t)==ENG_OK);pos=12;
        for(i=0;i<7;i++) {
            unsigned bytes=b16(data.map+32+12*i+4);
            assert(!memcmp(f.memory+(row_addr(i)-BASE),block+pos,bytes));pos+=bytes;
        }
        assert(f.settings[0x6dd]==block[10] && f.settings[0x6de]==block[11]);
        verify_neighbors();count++;
    }
    assert(feof(in) && !fclose(in) && count==30);
    assert(eng_restore_stock()==ENG_OK);verify_stock();
    printf("golden: unit=%u, 30 six-axis vectors, all 408 row bytes match independent Python\n",f.unit);
}
static void metadata_order(void)
{
    uint8_t *ids=(uint8_t *)data.ids,*m=(uint8_t *)eng_meta_record(&data,1);
    EngRecipeRef r;EngTweak t;int8_t lo[8],hi[8],def[8];unsigned w;
    ids[3]=5;ids[19]=1;m[14]=2;
    init();assert(eng_parameter_index(1)==4 && eng_parameter_index(5)==0);
    assert(eng_metadata(1,lo,hi,def)==ENG_OK && def[4]==2);
    assert(eng_menu_open()==ENG_OK && eng_select(1)==ENG_OK);
    assert(eng_current(&r,&t)==ENG_OK && t.v[4]==2);
    w=f.w;t.v[0]=1;assert(eng_apply(&r,&t)==ENG_OK && f.w==w && f.settings[0x6dd]==10);
    printf("metadata: unit=%u, reordered IDs and nonzero Default, WB avoids W\n",f.unit);
}
static void wide_wb(void)
{
    uint8_t *m=(uint8_t *)eng_meta_record(&data,1);EngRecipeRef r;EngTweak t={{0}};
    int8_t lo[8],hi[8],def[8];unsigned w;
    m[12]=m[15]=240;m[13]=m[16]=16;
    init();assert(eng_metadata(1,lo,hi,def)==ENG_OK && lo[4]==-16 && hi[4]==16);
    r=ref(1);assert(eng_apply(&r,&t)==ENG_OK);w=f.w;t.v[4]=16;t.v[5]=-16;
    assert(eng_apply(&r,&t)==ENG_OK && f.w==w && f.settings[0x6dd]==17 && f.settings[0x6de]==17);
    t.v[4]=-16;t.v[5]=16;
    assert(eng_apply(&r,&t)==ENG_OK && f.w==w && f.settings[0x6dd]==1 && f.settings[0x6de]==1);
    printf("WB: signed metadata +/-16; physical bytes clamp to 1..17 with zero deep W\n");
}
static void short_settings(void)
{
    EngRecipeRef r;EngTweak t={{0}};init();r=ref(1);f.short_settings=1;
    assert(eng_apply(&r,&t)==ENG_STALE && !f.w && !f.patch && !f.preview && f.releases==1);
    printf("S: short snapshot refused and released before W\n");
}
static void identity(void)
{
    EngRecipeRef r;EngTweak t={{0}};unsigned i,w;init();assert(eng_menu_open()==ENG_OK);assert(eng_select(4)==ENG_OK);r=ref(1);
    w=f.w;for(i=0;i<49;i++){r.identity[i]^=1;assert(eng_apply(&r,&t)==ENG_REJECTED);r.identity[i]^=1;}
    r.unit=(uint8_t)((f.unit+1)%3);assert(eng_apply(&r,&t)==ENG_REJECTED);assert(f.w==w && eng_list()->applied==4);
    assert(eng_select(17)==ENG_REJECTED && eng_list()->cursor==4);
    printf("identity: unit=%u, all 49 bytes and unit/slot rejection\n",f.unit);
}
static void rebind(void)
{
    init();eng_invalidate();assert(eng_rebind()==ENG_OK);assert(eng_menu_open()==ENG_OK);assert(eng_select(6)==ENG_OK);
    eng_invalidate();f.epochs[RV_LINK_E]++;assert(eng_rebind()==ENG_STALE);assert(!f.grain.armed);
    printf("rebind: unit=%u, full stock readback required; dirty reconnect rejected\n",f.unit);
}
static void reentry(void)
{
    EngPort p=port();f.core_reenter=1;
    assert(eng_init(image,image_bytes,&p)==ENG_OK && !f.core_reenter && !f.w && !f.patch);
    eng_invalidate();f.core_reenter=1;
    assert(eng_rebind()==ENG_OK && !f.core_reenter && !f.w && !f.patch);
    printf("reentry: pure init and rebind reject nested apply before W/S\n");
}
static void no_wb(void)
{
    EngPort p=port();EngRecipeRef r=ref(1);EngTweak t={{0}};unsigned w;
    memset(p.wb,0,sizeof(p.wb));assert(eng_init(image,image_bytes,&p)==ENG_OK);assert(eng_apply(&r,&t)==ENG_OK);
    w=f.w;t.v[4]=1;assert(eng_apply(&r,&t)==ENG_REJECTED && f.w==w);
    printf("WB: unit=%u, unbound axis refused before W/S/preview\n",f.unit);
}
static void pins(const char *kind)
{
    EngPort p;RvUnitInfo u;RvReply reply;
    if(!strcmp(kind,"bad-pin")) bad_pin=1;
    else if(!strcmp(kind,"stock-range")) {uint8_t *m=(uint8_t *)eng_meta_record(&data,4);m[0]=1;m[2]=1;}
    else if(!strcmp(kind,"old-sha")) ((uint8_t *)image)[b32(image+156)+64*f.unit+40]=1;
    else {
        uint8_t *record=(uint8_t *)eng_record(&data,4),*pool=(uint8_t *)data.pool;
        uint8_t id[49];uint32_t bank=(uint32_t)(data.bank-image);
        record[4]='X';eng_identity(record,id);p32(pool+16+4,eng_crc(id,49));
        p32(record+60,eng_crc(record,60));p32(image+bank+24,eng_crc(image+bank+32,1024));p32(image+bank+28,eng_crc(image+bank,28));
        p32(pool+12,eng_crc(pool+16,data.count*16));
    }
    reseal();make_gate();p=port();
    if(!strcmp(kind,"bad-entry-crc") || !strcmp(kind,"stock-range")) {Gxr2View full;assert(gxr2_semantic_validate(&gated,&host_trust,&full)==GXR2_OK);}
    assert(eng_init(image,image_bytes,&p)==ENG_REJECTED && !f.w && !f.patch && !f.preview && !f.begin);
    memset(&u,0,sizeof(u));mock(0,RV_UNIT,1,0,0,&u,sizeof(u),0,&reply);
    printf("pin: unit=%u %s rejected before T/S/W; map pin and entry CRC are independent\n",f.unit,kind);
}
static void size_caps(const char *kind)
{
    unsigned i,engine=!strcmp(kind,"cap24")?24576:!strcmp(kind,"cap32")?32768:!strcmp(kind,"cap32-over")?32772:16384,delta=engine-16;
    uint32_t directory;EngPort p;Gxr2View old_limit;Gxr2Unit unit;RvUnitInfo u;RvReply reply;
    assert(image_bytes+delta<=sizeof(image));
    memmove(image+272+delta,image+272,image_bytes-272);memset(image+272,0,delta);image_bytes+=delta;
    for(i=0;i<7;i++) {
        if(i==0) {p32(image+136,engine);gated.sections[0].length=engine;}
        else {p32(image+132+12*i,b32(image+132+12*i)+delta);gated.sections[i].offset+=delta;}
    }
    directory=b32(image+156);
    for(i=0;i<3;i++) {unsigned field;for(field=12;field<=24;field+=4)p32(image+directory+64*i+field,b32(image+directory+64*i+field)+delta);}
    p32(image+16,image_bytes);gated.length=image_bytes;reseal();
    if(!strcmp(kind,"cap32-over")) {
        assert(image_bytes<=49152 && eng_data_accept(&gated)==ENG_REJECTED && !f.w && !f.patch);
        printf("limits: engine=%u rejected before semantics and service writes\n",engine);return;
    }
    assert(eng_data_accept(&gated)==ENG_OK);
    memset(&u,0,sizeof(u));mock(0,RV_UNIT,1,0,0,&u,sizeof(u),0,&reply);
    assert(eng_data_validate(image,image_bytes,&u,&data)==ENG_OK);
    p=port();assert(eng_init(image,image_bytes,&p)==ENG_OK && !f.w && !f.patch);
    memcpy(unit.name,u.name,8);unit.main_version=0x151;unit.cmp_version=0;
    assert(gxr2_gate_validate(image,image_bytes,&host_trust,&unit,0,&old_limit)!=GXR2_OK);
    {Gxr2View invalid=gated;invalid.length=49156;assert(eng_data_accept(&invalid)==ENG_REJECTED);}
    printf("limits: engine=%u file=%u accepted by core semantics; upstream old gate rejects as expected\n",engine,image_bytes);
}
static void parser(void)
{
    RvUnitInfo u;RvReply reply;EngData out;unsigned i;uint32_t offset=b32(image+128+6*12+4);
    memset(&u,0,sizeof(u));mock(0,RV_UNIT,1,0,0,&u,sizeof(u),0,&reply);
    for(i=0;i<256;i++){memset(&out,0xa5,sizeof(out));assert(validate_pipeline(image,i,&u,&out)!=ENG_OK);}
    for(i=0;i<8;i++) {
        uint8_t saved=image[offset+32+4*i+3];image[offset+32+4*i+3]=9;reseal();assert(validate_pipeline(image,image_bytes,&u,&out)!=ENG_OK);image[offset+32+4*i+3]=saved;
    }
    for(i=256;i<image_bytes;i+=31) {
        memcpy(image,original,image_bytes);image[i]^=0x80;reseal();
        /* Engine bytes are resident's envelope responsibility, not semantic data. */
        if(i>=b32(image+128+4*12+4) && i<b32(image+128+6*12+4))
            assert(validate_pipeline(image,image_bytes,&u,&out)!=ENG_OK);
    }
    memcpy(image,original,image_bytes);
    printf("parser: all short headers, unknown IDs, semantic mutation stride 31\n");
}
static const RvApi *test_api;
static unsigned provided_calls;
static int32_t native_call(uint32_t sid,uint32_t op,const RvRequest *q,RvReply *r)
{
    provided_calls++;
    assert(q->version==1 && q->bytes==64 && !q->flags && q->args[0]==17 && q->args[1]==23);
    if(f.native_reenter && sid==RV_RPC8 && op==3) {
        RvRequest nested=*q;RvReply rejected;f.native_reenter=0;nested.args[8]=2;
        assert(eng_entry_event(test_api,17,&nested,&rejected)==RV_FAULT && rejected.status==RV_BUSY);
    }
    return mock(0,sid,op,q->args[8],q->args[9],eng_wire_pointer(q->args[10]),q->args[11],q->args[12],r);
}
static int32_t wrong_provider(uint32_t sid,uint32_t op,const RvRequest *q,RvReply *r)
{
    (void)sid;(void)op;(void)q;(void)r;assert(!"dispatch escaped the init RvApi");return RV_FAULTED;
}
static void entries(int fail)
{
    RvApi api;RvRequest q;RvReply r;RvEngineEntries ent={0};EngInitWire initwire;
    memset(&api,0,sizeof(api));api.version=1;api.bytes=sizeof(api);api.call=native_call;test_api=&api;
    memset(&q,0,sizeof(q));q.version=1;q.bytes=64;q.args[0]=17;q.args[1]=23;
    q.args[10]=eng_wire_address(&ent);q.args[11]=sizeof(ent);
    assert(eng_bootstrap(&api,17,&q,&r)==RV_CONSUMED && r.actual==40 && ent.init && ent.abort);
    memset(&initwire,0,sizeof(initwire));initwire.header.version=1;initwire.header.bytes=sizeof(initwire);
    initwire.image_address=eng_wire_address(image);initwire.image_bytes=image_bytes;
    initwire.grain_address=eng_wire_address(&f.grain);initwire.grain_bytes=32;
    initwire.gate_view_address=eng_wire_address(&gated);initwire.gate_view_bytes=sizeof(gated);
    q.args[10]=eng_wire_address(&initwire);q.args[11]=sizeof(initwire);
    assert(eng_entry_init(&api,17,&q,&r)==RV_CONSUMED && !f.w && !f.patch && !f.ui_binds);
    q.args[10]=q.args[11]=0;
    {
        RvApi wrong=api;unsigned calls=provided_calls;wrong.call=wrong_provider;
        assert(calls && eng_entry_menu(&wrong,17,&q,&r)==RV_FAULT && provided_calls==calls && !f.ui_binds);
    }
    assert(eng_entry_menu(&api,17,&q,&r)==RV_CONSUMED && f.ui_binds==1 && f.texts==16);
    assert(provided_calls>1);
    f.native_reenter=1;
    q.args[8]=1;q.args[9]=1;assert(eng_entry_event(&api,17,&q,&r)==RV_CONSUMED && f.patch==1);
    q.args[8]=1;q.args[9]=2;assert(eng_entry_apply(&api,17,&q,&r)==RV_CONSUMED && f.preview==2);
    q.args[8]=1;q.args[9]=257;assert(eng_entry_event(&api,17,&q,&r)==RV_CLOSE_AND_PASS && f.last_ui_cursor==1);
    if(fail) {
        unsigned w;RvEngineEntry stop=(RvEngineEntry)(uintptr_t)eng_wire_pointer(ent.abort);
        f.fail_w=f.w+1;q.args[8]=1;q.args[9]=6;
        assert(eng_entry_event(&api,17,&q,&r)==RV_FAULT && f.last_ui_cursor==1);
        w=f.w;assert(stop(&api,17,&q,&r)==RV_FAULT && f.w==w && eng_uncertain());
        printf("entries failure: cursor rolled back in native descriptor; abort preserves uncertain\n");return;
    }
    q.args[8]=2;assert(eng_entry_event(&api,17,&q,&r)==RV_CONSUMED && f.ui_releases==1);
    {
        RvEngineEntry stop=(RvEngineEntry)(uintptr_t)eng_wire_pointer(ent.shutdown);
        assert(stop(&api,17,&q,&r)==RV_PASS);verify_stock();
    }
    printf("entries: init RvApi dispatch (%u calls), replacement table rejected; bootstrap/init/menu/select/edit/close/stock shutdown, 16 glyph labels\n",provided_calls);
}
int main(int argc,char **argv)
{
    FILE *in;unsigned unit,at;
    assert(argc==5);in=fopen(argv[1],"rb");assert(in);image_bytes=(uint32_t)fread(image,1,sizeof(image),in);assert(feof(in));assert(!fclose(in));memcpy(original,image,image_bytes);
    {
        uint8_t wire[232];unsigned i;FILE *trust=fopen(getenv("ENG_CORE_TRUST"),"rb");assert(trust);
        assert(fread(wire,1,232,trust)==232 && fgetc(trust)==EOF && !fclose(trust));assert(!memcmp(wire,"GXTRUST2",8));
        memcpy(host_trust.body_sha256,wire+8,32);memcpy(host_trust.resident_build_id,wire+40,32);memcpy(host_trust.resident_abi_id,wire+72,16);
        for(i=0;i<3;i++){const uint8_t *m=wire+88+48*i;memcpy(host_trust.modules[i].unit.name,m,8);
            host_trust.modules[i].unit.main_version=b16(m+8);host_trust.modules[i].unit.cmp_version=b16(m+10);
            host_trust.modules[i].stock_crc32=b32(m+12);memcpy(host_trust.modules[i].stock_sha256,m+16,32);}
    }
    unit=(unsigned)strtoul(argv[3],0,10);at=(unsigned)strtoul(argv[4],0,10);assert(unit<3);setup(unit);
    if(!strcmp(argv[2],"slots"))slots();else if(!strcmp(argv[2],"tweaks"))tweaks();
    else if(!strcmp(argv[2],"t1"))t1();else if(!strncmp(argv[2],"startup",7))startup_test(argv[2]);
    else if(!strcmp(argv[2],"grain"))grain();else if(!strcmp(argv[2],"identity"))identity();else if(!strcmp(argv[2],"golden"))golden();else if(!strcmp(argv[2],"metadata"))metadata_order();else if(!strcmp(argv[2],"short-s"))short_settings();else if(!strcmp(argv[2],"wide-wb"))wide_wb();
    else if(!strcmp(argv[2],"rebind"))rebind();else if(!strcmp(argv[2],"reentry"))reentry();else if(!strcmp(argv[2],"no-wb"))no_wb();
    else if(!strcmp(argv[2],"parser"))parser();
    else if(!strcmp(argv[2],"bad-pin") || !strcmp(argv[2],"old-sha") || !strcmp(argv[2],"bad-entry-crc") || !strcmp(argv[2],"stock-range"))pins(argv[2]);
    else if(!strcmp(argv[2],"cap24") || !strcmp(argv[2],"cap32") || !strcmp(argv[2],"cap32-over") || !strcmp(argv[2],"cap48"))size_caps(argv[2]);else if(!strcmp(argv[2],"entries"))entries(0);else if(!strcmp(argv[2],"entries-failure"))entries(1);else failure(argv[2],at);
    return 0;
}
