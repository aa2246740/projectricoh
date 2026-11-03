#include <assert.h>
#include <limits.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "ui_v2_data.h"
#include "window_function.inc.c"

uint32_t gxr2_crc_zeroed(const uint8_t *p,size_t n,size_t start,size_t count)
{
    uint32_t crc=~0u;size_t i;unsigned bit;
    for(i=0;i<n;++i){crc^=(i>=start&&i-start<count)?0:p[i];
        for(bit=0;bit<8;++bit)crc=(crc>>1)^((crc&1)?0xedb88320u:0);}
    return ~crc;
}
int main(int argc,char **argv)
{
    FILE *stream;long length;uint8_t *raw;KvDataView view;
    unsigned count,current,previous,unit,slot,screen,physical,i;
    unsigned windows=0,edges=0,nonadjacent=0,clamps=0;
    assert(argc==2);stream=fopen(argv[1],"rb");assert(stream);
    assert(!fseek(stream,0,SEEK_END));length=ftell(stream);rewind(stream);
    assert(length>KV_DATA_BYTES);raw=malloc((size_t)length);assert(raw);
    assert(fread(raw,1,(size_t)length,stream)==(size_t)length&&!fclose(stream));
    assert(!kv_data_open(raw+length-KV_DATA_BYTES,KV_DATA_BYTES,&view));
    for(count=1;count<=33;++count)for(current=0;current<count;++current)for(previous=0;previous<=256;++previous){
        KvUiWindow w;assert(!kv_ui_window(count,current,previous==256?UINT_MAX:previous,&w));
        assert(w.cursor<8&&w.top+w.cursor==current&&w.top<=(count>8?count-8:0));
        assert(count>8||!w.top);++windows;
    }
    for(unit=0;unit<3;++unit)for(slot=1;slot<=8;++slot)for(screen=0;screen<3;++screen){
        UvLevels levels,out;KvUiNav nav,next;KvUiWindow w;
        assert(!kv_ui_default(&view,unit,slot,&levels));
        assert(!kv_ui_nav_init(&view,unit,slot,&levels,&nav));nav.screen=screen;
        count=kv_ui_count(&view,unit,slot,screen,nav.control);assert(count>2);
        nav.current[screen]=0;nav.top[screen]=0;
        assert(!kv_ui_native_move(&view,unit,slot,&levels,&nav,2,&out,&next));
        assert(next.current[screen]==2&&!memcmp(&out,&levels,sizeof(out)));++nonadjacent;
        assert(!kv_ui_window(count,0,0,&w));physical=(w.cursor+7u)%8u;
        assert(!kv_ui_native_move(&view,unit,slot,&levels,&nav,physical,&out,&next));
        assert(next.current[screen]==count-1);++edges;
        nav=next;assert(!kv_ui_window(count,count-1,nav.top[screen],&w));physical=(w.cursor+1u)%8u;
        assert(!kv_ui_native_move(&view,unit,slot,&levels,&nav,physical,&out,&next));
        assert(!next.current[screen]);++edges;
        if(screen)continue;
        for(i=0;i<2;++i){
            KvDataItem item;KvDataPoint point;int direction=i?-1:1;
            unsigned control=i?1:0;
            if(kv_data_find(&view,unit,slot,control,&item))continue;
            assert(!kv_ui_nav_init(&view,unit,slot,&levels,&nav));nav.screen=KV_UI_VALUE;nav.control=control;
            count=item.point_count;
            for(current=0;current<2;++current){
                nav.current[KV_UI_VALUE]=current?count-1:0;
                assert(!kv_data_point(&view,&item,count-1-nav.current[KV_UI_VALUE],&point));
                levels.v[control]=point.level;
                assert(!kv_ui_window(count,nav.current[KV_UI_VALUE],0,&w));nav.top[KV_UI_VALUE]=w.top;
                physical=(w.cursor+(current?1u:7u))%8u;
                assert(!kv_ui_native_move(&view,unit,slot,&levels,&nav,physical,&out,&next));
                assert(next.current[KV_UI_VALUE]==nav.current[KV_UI_VALUE]&&!memcmp(&out,&levels,sizeof(out)));
                ++clamps;
            }
            (void)direction;
            assert(!kv_ui_default(&view,unit,slot,&levels));
        }
    }
    printf("{\"status\":\"PASS_HOST\",\"windows\":%u,\"menu_edges\":%u,\"nonadjacent_moves\":%u,\"value_clamps\":%u,\"L1_0_to_physical_2\":2}\n",windows,edges,nonadjacent,clamps);
    free(raw);return 0;
}
