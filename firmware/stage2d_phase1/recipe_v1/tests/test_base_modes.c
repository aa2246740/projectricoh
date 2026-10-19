#include "recipe_v1.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define CHECK(x) do { if (!(x)) { fprintf(stderr,"%s:%d: %s\n",__FILE__,__LINE__,#x); exit(1); } } while (0)
static unsigned cases;
static uint8_t settings[4096], expected[4096];
static unsigned previews, releases;
static int preview_error;
static Rv1Status acquire(void *context, volatile uint8_t **s, size_t *length)
{ (void)context; *s = settings; *length = sizeof(settings); return RV1_OK; }
static Rv1Status preview(void *context)
{
    (void)context;
    CHECK(memcmp(settings, expected, sizeof(settings)) == 0);
    ++previews;
    return preview_error ? RV1_IO : RV1_OK;
}
static void release(void *context, int changed)
{ (void)context; CHECK(changed == 1); ++releases; }
static void put32(uint8_t *p, uint32_t v)
{ p[0]=(uint8_t)(v>>24); p[1]=(uint8_t)(v>>16); p[2]=(uint8_t)(v>>8); p[3]=(uint8_t)v; }
static void crc(uint8_t *file)
{
    unsigned i;
    for (i=0;i<16;++i) put32(file+32+i*64+60,rv1_crc32(file+32+i*64,60));
    put32(file+24,rv1_crc32(file+32,1024)); put32(file+28,rv1_crc32(file,28));
}
static Rv1Recipe recipe(uint8_t mode)
{
    Rv1Recipe r;
    memset(&r,0,sizeof(r)); r.name_length=2; r.name[0]='B'; r.name[1]='W';
    r.base_mode=mode; r.raw[0]=8; r.raw[1]=4; r.wb[0]=-8; r.wb[1]=8;
    if(mode==4) memset(r.raw,3,13);
    if(mode==6) { r.raw[2]=7; r.raw[3]=6; }
    return r;
}

int main(void)
{
    const uint8_t modes[]={4,3,6}, tones[]={6,1,2,3,4};
    const uint16_t color[]={0x36f,0x370,0x371,0x8ac,0x8ad,0x8ae,0x8af,0x8b0,0x8b1,0x8b2,0x8b3,0x8b4,0x8b5};
    const uint16_t bw[]={0x645,0x646}, te[]={0x641,0x642,0x644,0x643};
    Rv1SettingsPort port={NULL,acquire,preview,release};
    Rv1Bank bank,out,sentinel;
    uint8_t file[1056], good[1056];
    unsigned m,t,i,v;
    CHECK(sizeof(Rv1Recipe)==49);
    for(m=0;m<3;++m) {
        unsigned n=m==0?13:m==1?2:4;
        const uint16_t *offsets=m==0?color:m==1?bw:te;
        for(t=0;t<(m==2?5u:1u);++t) for(v=1;v<=9;++v) {
            Rv1Recipe r=recipe(modes[m]);
            Rv1WritePlan plan;
            r.raw[0]=(uint8_t)v;
            if(m==2) r.raw[3]=tones[t];
            rv1_bank_init(&bank); bank.slots[15].occupied=1; bank.slots[15].recipe=r;
            CHECK(rv1_encode(&bank,17,file,sizeof(file))==RV1_OK);
            CHECK(memcmp(file,"GXRRV201\0\2\0\40\0\100\0\20",16)==0);
            CHECK(file[995]==modes[m]);
            CHECK(rv1_decode(file,sizeof(file),&out,NULL)==RV1_OK);
            CHECK(memcmp(&out.slots[15].recipe,&r,sizeof(r))==0);
            CHECK(rv1_plan(&r,&plan)==RV1_OK && plan.count==n+3);
            for(i=0;i<n;++i) CHECK(plan.writes[i].offset==offsets[i] && plan.writes[i].value==r.raw[i]);
            CHECK(plan.writes[n].offset==0x6dd && plan.writes[n].value==1);
            CHECK(plan.writes[n+1].offset==0x6de && plan.writes[n+1].value==17);
            CHECK(plan.writes[n+2].offset==0x36e && plan.writes[n+2].value==modes[m]);
            memset(settings,0xa5,sizeof(settings)); memcpy(expected,settings,sizeof(settings));
            for(i=0;i<n;++i) expected[offsets[i]]=r.raw[i];
            expected[0x6dd]=1;expected[0x6de]=17;expected[0x36e]=modes[m];
            preview_error=0;CHECK(rv1_apply(&port,&r)==RV1_OK);
            preview_error=1;CHECK(rv1_apply(&port,&r)==RV1_IO);
            CHECK(previews==releases);
            ++cases;
        }
    }
    /* Semantic mutations have valid CRCs, so CRC failure cannot mask them. */
    rv1_bank_init(&bank); bank.slots[0].occupied=1; bank.slots[0].recipe=recipe(3);
    CHECK(rv1_encode(&bank,1,good,sizeof(good))==RV1_OK);
    memset(&sentinel,0xa5,sizeof(sentinel));
    for(i=0;i<13;++i) {
        if(i<2) continue;
        memcpy(file,good,sizeof(file)); file[68+i]=1;crc(file);out=sentinel;
        CHECK(rv1_decode(file,sizeof(file),&out,NULL)==RV1_CORRUPT);
        CHECK(memcmp(&out,&sentinel,sizeof(out))==0);
    }
    memcpy(file,good,sizeof(file));file[35]=9;crc(file);
    CHECK(rv1_decode(file,sizeof(file),NULL,NULL)==RV1_VERSION);++cases;
    bank.slots[0].recipe=recipe(6);CHECK(rv1_encode(&bank,1,good,sizeof(good))==RV1_OK);
    for(i=0;i<=9;++i) if(i==0||i==5||i>=7) {
        memcpy(file,good,sizeof(file));file[71]=(uint8_t)i;crc(file);
        CHECK(rv1_decode(file,sizeof(file),NULL,NULL)==RV1_RANGE);
    }
    for(i=4;i<13;++i) {
        memcpy(file,good,sizeof(file));file[68+i]=1;crc(file);
        CHECK(rv1_decode(file,sizeof(file),NULL,NULL)==RV1_CORRUPT);
    }
    ++cases;
    /* Names containing BW remain color on explicit v1 import. */
    bank.slots[0].recipe=recipe(4);CHECK(rv1_encode(&bank,1,file,sizeof(file))==RV1_OK);
    file[5]='1';file[9]=1;file[35]=0;crc(file);
    CHECK(rv1_decode(file,sizeof(file),NULL,NULL)==RV1_VERSION);
    CHECK(rv1_import_v1(file,sizeof(file),&out)==RV1_OK);
    CHECK(out.slots[0].recipe.base_mode==4 && out.slots[0].recipe.name[0]=='B');
    CHECK(rv1_encode(&out,2,good,sizeof(good))==RV1_OK && good[35]==4);++cases;
    file[70]=10;crc(file);out=sentinel;
    CHECK(rv1_import_v1(file,sizeof(file),&out)==RV1_RANGE);
    CHECK(memcmp(&out,&sentinel,sizeof(out))==0);++cases;
    /* Native Standard publishes only the selector and the two WB axes. */
    {
        Rv1Recipe r=recipe(1); Rv1WritePlan plan;
        memset(r.raw,0,sizeof(r.raw));
        CHECK(rv1_plan(&r,&plan)==RV1_OK && plan.count==3);
        CHECK(plan.writes[0].offset==0x6dd && plan.writes[0].value==1);
        CHECK(plan.writes[1].offset==0x6de && plan.writes[1].value==17);
        CHECK(plan.writes[2].offset==0x36e && plan.writes[2].value==1);
        memset(settings,0xa5,sizeof(settings)); memcpy(expected,settings,sizeof(settings));
        expected[0x6dd]=1; expected[0x6de]=17; expected[0x36e]=1;
        preview_error=0; CHECK(rv1_apply(&port,&r)==RV1_OK);
        CHECK(settings[0x36f]==0xa5 && settings[0x8ac]==0xa5 && settings[0x645]==0xa5 && settings[0x641]==0xa5);
        r.raw[0]=1; CHECK(rv1_validate_recipe(&r)==RV1_CORRUPT);
        ++cases;
    }
    printf("RESULT %u base-mode cases passed; entire-S comparisons include RAW, scene and Setting2\n",cases);
    return 0;
}
