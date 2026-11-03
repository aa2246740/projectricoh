#define main builder_fixture_main
#include "worktree/firmware/recipe_fw/tests/test_host.c"
#undef main

static unsigned extra_cases;
static void put_be32(uint8_t *p, uint32_t v)
{ p[0]=(uint8_t)(v>>24);p[1]=(uint8_t)(v>>16);p[2]=(uint8_t)(v>>8);p[3]=(uint8_t)v; }
static void seal(uint8_t *p)
{
    unsigned i;
    for(i=0;i<16;++i)put_be32(p+32+i*64+60,rv1_crc32(p+32+i*64,60));
    put_be32(p+24,rv1_crc32(p+32,1024));put_be32(p+28,rv1_crc32(p,28));
}
static void mode_bank(unsigned index, uint32_t generation, unsigned mode)
{
    Rv1Bank bank;
    unsigned i;
    make_bank(index,generation,3);
    CHECK(rv1_decode(files[index].bytes,1056,&bank,NULL)==RV1_OK);
    for(i=0;i<16;++i){
        Rv1Recipe *r=&bank.slots[i].recipe;
        r->base_mode=(uint8_t)mode;memset(r->raw,0,13);
        r->raw[0]=3;r->raw[1]=4;r->wb[0]=-8;r->wb[1]=8;
        if(mode==6){r->raw[2]=5;r->raw[3]=6;}
    }
    CHECK(rv1_encode(&bank,generation,files[index].bytes,1120)==RV1_OK);
}
static void reject_without_write(void)
{
    uint8_t before[4096], media[1056];
    int n=previews;
    memcpy(before,settings_a,sizeof(before));memcpy(media,files[0].bytes,1056);
    CHECK(rfw_open()==1);
    CHECK(rfw_select(1)!=RV1_OK);
    CHECK(rfw_select(16)!=RV1_OK);
    CHECK(memcmp(before,settings_a,sizeof(before))==0 && previews==n);
    CHECK(memcmp(media,files[0].bytes,1056)==0 && writing==0);
    ++extra_cases;
}
int main(void)
{
    unsigned mode,slot,i,j;
    const unsigned bad_modes[]={0,1,5,7,255};
    const unsigned invalid_raw[]={0,10,255};
    for(mode=3;mode<=6;mode+=3) for(slot=0;slot<16;slot+=15){
        unsigned row=32+64*slot;
        for(i=0;i<5;++i){
            reset();mode_bank(0,2,mode);files[0].bytes[row+3]=(uint8_t)bad_modes[i];
            seal(files[0].bytes);reject_without_write();
        }
        for(i=0;i<(mode==3?2u:3u);++i)for(j=0;j<3;++j){
            reset();mode_bank(0,2,mode);files[0].bytes[row+36+i]=(uint8_t)invalid_raw[j];
            seal(files[0].bytes);reject_without_write();
        }
        for(i=(mode==3?2u:4u);i<13;++i){
            reset();mode_bank(0,2,mode);files[0].bytes[row+36+i]=1;
            seal(files[0].bytes);reject_without_write();
        }
        for(i=0;i<2;++i){
            reset();mode_bank(0,2,mode);files[0].bytes[row+49+i]=9;
            seal(files[0].bytes);reject_without_write();
        }
        if(mode==6)for(i=0;i<8;++i){
            static const uint8_t tones[]={0,5,7,8,9,127,128,255};
            reset();mode_bank(0,2,mode);files[0].bytes[row+39]=tones[i];
            seal(files[0].bytes);reject_without_write();
        }
        reset();mode_bank(0,2,mode);files[0].bytes[row+60]^=1;reject_without_write();
        reset();mode_bank(0,2,mode);files[0].bytes[24]^=1;
        put_be32(files[0].bytes+28,rv1_crc32(files[0].bytes,28));reject_without_write();
        reset();mode_bank(0,2,mode);files[0].bytes[28]^=1;reject_without_write();
        reset();mode_bank(0,2,mode);files[0].length=1055;reject_without_write();
        reset();mode_bank(0,2,mode);files[0].length=1057;reject_without_write();
    }
    reset();mode_bank(0,1,3);mode_bank(1,2,6);
    files[1].bytes[68]=10;seal(files[1].bytes);
    CHECK(rfw_open()==1 && rfw_select(1)==RV1_OK && settings_a[0x36e]==3);
    CHECK(settings_a[0x645]==3 && settings_a[0x646]==4);++extra_cases;
    reset();mode_bank(0,1,3);mode_bank(1,2,6);
    files[1].bytes[35]=5;seal(files[1].bytes);
    reject_without_write(); /* Unknown format/mode companion blocks the view. */
    reset();mode_bank(0,1,3);mode_bank(1,1,6);reject_without_write();
    reset();mode_bank(1,1,6);
    CHECK(rfw_open()==1 && rfw_select(1)==RV1_OK && settings_a[0x36e]==6);++extra_cases;
    reset();make_bank(0,1,3);files[0].bytes[5]='1';files[0].bytes[9]=1;
    for(i=0;i<16;++i)files[0].bytes[35+i*64]=0;
    seal(files[0].bytes);reject_without_write();
    reset();
    printf("RESULT %u additional GUI/parser no-write and mixed-bank cases passed\n",extra_cases);
    return 0;
}
