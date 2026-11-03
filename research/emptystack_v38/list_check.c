#include <assert.h>
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "kv_ui.h"

static unsigned long windows, moves, frames, fillers, endpoints;
extern unsigned long adapter_checks(void);

static void window_checks(void)
{
    unsigned count, cur, prev, physical;
    for(count=1;count<=33;++count)for(cur=0;cur<count;++cur)for(prev=0;prev<=256;++prev){
        KvUiWindow w;KvUiFrame f;
        unsigned previous=prev==256?UINT_MAX:prev;
        assert(!kv_ui_window(count,cur,previous,&w));
        assert(w.cursor==cur-w.top&&w.cursor<8&&w.top<=(count>8?count-8:0));
        assert(count>8||w.top==0);
        assert(!kv_ui_layout(count,cur,previous,&f));
        assert(f.rows==8&&f.cursor==w.cursor&&f.top==w.top);
        for(physical=0;physical<8;++physical)
            assert(!!(f.selectable&(1u<<physical))==(w.top+physical<count));
        ++windows;
    }
}

static void frame_check(const KvDataView *v,const KvUiModel *model,const KvUiNav *nav)
{
    unsigned row;
    KvUiFrame f;
    assert(!kv_ui_render(v,model,nav,&f));
    assert(f.rows==8&&f.cursor<8&&f.top+f.cursor==nav->current[nav->screen]);
    for(row=0;row<8;++row){
        unsigned logical=f.top+row;
        assert(memchr(f.text[row],0,9)!=NULL&&strlen(f.text[row])<=8);
        assert(!!(f.selectable&(1u<<row))==(logical<f.logical_count));
        if(logical==f.logical_count){assert(!strcmp(f.text[row],"--------"));++fillers;}
        if(logical>f.logical_count)assert(f.text[row][0]==' '&&f.text[row][1]==0);
        if(logical>=f.logical_count){
            UvLevels levels;KvUiNav next;KvUiEvent e;
            assert(!kv_ui_native_disp(v,model->unit,model->slot,model->levels,nav,row,&levels,&next,&e));
            assert(e.kind==KV_UI_EVENT_NONE&&!memcmp(&next,nav,sizeof(next)));
            assert(!memcmp(&levels,model->levels,sizeof(levels)));
        }
    }
    ++frames;
}

static void menu_checks(const KvDataView *v)
{
    unsigned unit,slot,screen,control,cur,count,i;
    static const char *const names[8]={"GRPos","GRNeg","HC BW","Std","F-CC","F-CN","L-Chr","L-Vi"};
    for(unit=0;unit<3;++unit){
        UvLevels cache[8];
        for(slot=1;slot<=8;++slot)assert(!kv_ui_default(v,unit,slot,&cache[slot-1]));
        for(slot=1;slot<=8;++slot)for(screen=0;screen<KV_UI_SCREENS;++screen)
        for(control=0;control<(screen==KV_UI_VALUE?10u:1u);++control){
            count=kv_ui_count(v,unit,slot,screen,control);
            if(!count)continue;
            for(cur=0;cur<count;++cur){
                UvLevels levels=cache[slot-1];KvUiNav nav;
                assert(!kv_ui_nav_init(v,unit,slot,&levels,&nav));
                nav.screen=(uint8_t)screen;nav.control=(uint8_t)control;nav.current[screen]=(uint8_t)cur;
                if(screen==KV_UI_VALUE){
                    KvDataItem item;KvDataPoint point;
                    assert(!kv_data_find(v,unit,slot,control,&item));
                    assert(!kv_data_point(v,&item,count-1-cur,&point));levels.v[control]=point.level;
                }
                {KvUiModel model={unit,slot,slot,0,&levels,cache,names};frame_check(v,&model,&nav);}
                for(i=0;i<14;++i){
                    int delta=i<7?-(int)(i+1):(int)(i-6);
                    int expected=(int)cur+delta;
                    UvLevels out;KvUiNav next;KvUiWindow w;
                    if(screen==KV_UI_VALUE){if(expected<0)expected=0;if(expected>=(int)count)expected=(int)count-1;}
                    else{expected%=(int)count;if(expected<0)expected+=(int)count;}
                    nav.armed=1;
                    assert(!kv_ui_move(v,unit,slot,&levels,&nav,delta,&out,&next));
                    assert(next.current[screen]==expected&&next.armed==0);
                    assert(!kv_ui_window(count,(unsigned)expected,nav.top[screen],&w));
                    assert(next.top[screen]==w.top);
                    if(screen!=KV_UI_VALUE)assert(!memcmp(&out,&levels,sizeof(out)));
                    if(screen==KV_UI_VALUE&&(cur==0||cur+1==count)&&expected==(int)cur){
                        char text[9];assert(!memcmp(&out,&levels,sizeof(out)));
                        assert(!kv_ui_value(v,unit,slot,control,out.v[control],text));
                        assert(strchr(text,'!'));++endpoints;
                    }
                    ++moves;
                }
            }
        }
    }
}

int main(int argc,char **argv)
{
    FILE *f;long length;uint8_t *bytes;KvDataView view;
    assert(argc==2);f=fopen(argv[1],"rb");assert(f);
    assert(!fseek(f,0,SEEK_END));length=ftell(f);assert(length>KV_DATA_BYTES);rewind(f);
    bytes=malloc((size_t)length);assert(bytes&&fread(bytes,1,(size_t)length,f)==(size_t)length);fclose(f);
    assert(!kv_data_open(bytes+length-KV_DATA_BYTES,KV_DATA_BYTES,&view));
    window_checks();menu_checks(&view);
    printf("{\"status\":\"PASS\",\"windows\":%lu,\"moves\":%lu,\"frames\":%lu,\"fillers\":%lu,\"endpoints\":%lu,\"adapter_moves\":%lu}\n",windows,moves,frames,fillers,endpoints,adapter_checks());
    free(bytes);return 0;
}
