#include "knobs.h"
#include "menu.h"
#include "../tables/knobs_v2_r2_tables.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static uint32_t state=UINT32_C(0x6b327231);
static uint32_t rng(void){state^=state<<13;state^=state>>17;state^=state<<5;return state;}
int main(int argc,char **argv)
{
    FILE *f;uint8_t entries[24][2][KV_BYTES],saved[24][2][KV_BYTES];
    struct {uint8_t pre[16],out[KV_BYTES],post[16];} guarded;
    KvRequest r={100,{0},0,0};KvStats st;unsigned i,j,which;int rc;
    if(argc!=2 || !(f=fopen(argv[1],"rb")))return 2;
    if(fread(entries,1,sizeof(entries),f)!=sizeof(entries)){fclose(f);return 3;}fclose(f);memcpy(saved,entries,sizeof(entries));
    for(i=0;i<20000;i++){
        which=rng()%24;r.amount=(int32_t)(rng()%16)*10;r.wb_method=(int32_t)(rng()%2);r.tone_method=(int32_t)(rng()%2);
        for(j=0;j<10;j++){int lim=(j<3 || j==4)?16384:4096;r.dose[j]=(int32_t)(rng()%(unsigned)(2*lim+1))-lim;}
        r.dose[KV_FADE]=(int32_t)(rng()%4097);
        memset(&guarded,0xa5,sizeof(guarded));rc=kv_apply(entries[which][0],entries[which][1],&r,guarded.out,&st);
        if(rc)return 10;
        for(j=0;j<16;j++)if(guarded.pre[j]!=0xa5 || guarded.post[j]!=0xa5)return 11;
    }
    if(memcmp(saved,entries,sizeof(entries)))return 12;
    memset(&guarded,0xa5,sizeof(guarded));r.amount=151;
    if(kv_apply(entries[0][0],entries[0][1],&r,guarded.out,&st)!=-1)return 13;
    for(j=0;j<KV_BYTES;j++)if(guarded.out[j]!=0xa5)return 14;
    r.amount=100;r.dose[0]=16385;
    if(kv_apply(entries[0][0],entries[0][1],&r,guarded.out,&st)!=-1)return 15;
    if(kv_apply(NULL,entries[0][1],&r,guarded.out,&st)!=-1)return 16;
    for(i=0;i<20000;i++){
        int16_t levels[9];int recipe_index=(int)(rng()%KV2_RECIPE_COUNT);
        const Kv2Recipe *recipe=&kv2_recipes[recipe_index];
        for(j=0;j<(unsigned)recipe->item_count;j++){
            const Kv2Item *item=&kv2_items[recipe->first_item+j];
            levels[j]=item->points[rng()%(unsigned)item->point_count].level;
        }
        memset(&guarded,0xa5,sizeof(guarded));
        rc=kv2_apply(recipe->unit,recipe->slot,levels,recipe->item_count,entries[recipe_index][0],entries[recipe_index][1],guarded.out,&st);
        if(rc)return 17;
        for(j=0;j<16;j++)if(guarded.pre[j]!=0xa5 || guarded.post[j]!=0xa5)return 18;
        levels[0]=32767;memset(&guarded,0xa5,sizeof(guarded));
        if(kv2_apply(recipe->unit,recipe->slot,levels,recipe->item_count,entries[recipe_index][0],entries[recipe_index][1],guarded.out,&st)!=-1)return 19;
        for(j=0;j<KV_BYTES;j++)if(guarded.out[j]!=0xa5)return 20;
    }
    if(memcmp(saved,entries,sizeof(entries)))return 21;
    puts("PASS ASan+UBSan: 20000 full-domain core + 20000 menu requests, guards, immutable inputs, invalid requests");
    return 0;
}
