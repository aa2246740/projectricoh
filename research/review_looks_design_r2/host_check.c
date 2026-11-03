#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "kv_data.h"

#define API(P) \
int P##kv_data_open(const uint8_t *,size_t,KvDataView *); \
int P##kv_data_recipe(const KvDataView *,unsigned,unsigned,KvDataRecipe *); \
int P##kv_data_item(const KvDataView *,unsigned,KvDataItem *); \
int P##kv_data_find(const KvDataView *,unsigned,unsigned,unsigned,KvDataItem *); \
int P##kv_data_point(const KvDataView *,const KvDataItem *,unsigned,KvDataPoint *); \
int P##kv_data_request(const KvDataView *,unsigned,unsigned,const UvLevels *,KvRequest *); \
int P##kv_ui_value(const KvDataView *,unsigned,unsigned,unsigned,int,char [9]);
API(old_)
API(raw_)
API(r3_)
API(diag_)

static KvDataView ov,dv;
static uint8_t fixtures[24][552];
static unsigned long long request_cases,request_ok,request_rejected;
static unsigned long long row_cases,row_ok,row_rejected,text_cases,pair_cases;
static unsigned long long index_rejected,api_rejected;
static void require(int ok,const char *where)
{if(!ok){fprintf(stderr,"check failed at %s\n",where);exit(1);}}
static void read_file(const char *p,void *out,size_t n)
{FILE *f=fopen(p,"rb");require(f!=NULL,"fopen");require(fread(out,1,n,f)==n,"fread");require(fgetc(f)==EOF,"eof");require(!fclose(f),"fclose");}
static void rows(unsigned unit,unsigned slot,const KvRequest *a,const KvRequest *b)
{
    uint8_t x[552],y[552];KvStats xs,ys;KvWork xw,yw;int xr,yr;
    memset(x,0xa5,sizeof(x));memset(y,0xa5,sizeof(y));
    memset(&xs,0xa5,sizeof(xs));memset(&ys,0xa5,sizeof(ys));
    xr=kv_apply_work(fixtures[unit*8+3],fixtures[unit*8+slot-1],a,x,&xs,&xw);
    yr=kv_apply_work(fixtures[unit*8+3],fixtures[unit*8+slot-1],b,y,&ys,&yw);
    require(xr==yr,"math status");require(!memcmp(x,y,sizeof(x)),"552 bytes");
    require(!memcmp(&xs,&ys,sizeof(xs)),"math stats");
    ++row_cases;if(!xr)++row_ok;else{
        uint8_t unchanged[552];KvStats untouched;
        memset(unchanged,0xa5,sizeof(unchanged));memset(&untouched,0xa5,sizeof(untouched));
        require(!memcmp(x,unchanged,sizeof(x)),"failed math output unchanged");
        require(!memcmp(&xs,&untouched,sizeof(xs)),"failed math stats unchanged");
        ++row_rejected;
    }
}
static void request(unsigned unit,unsigned slot,const UvLevels *levels,int expected,int render)
{
    KvRequest a,b,untouched;int ar,br;
    memset(&a,0xa5,sizeof(a));memset(&b,0xa5,sizeof(b));memset(&untouched,0xa5,sizeof(untouched));
    ar=old_kv_data_request(&ov,unit,slot,levels,&a);
    br=diag_kv_data_request(&dv,unit,slot,levels,&b);
    require(ar==br,"request status");if(expected!=-2)require(ar==expected,"literal membership result");
    require(!memcmp(&a,&b,sizeof(a)),"52 request bytes");++request_cases;
    if(ar){require(!memcmp(&a,&untouched,sizeof(a)),"failed request unchanged");++request_rejected;}
    else {++request_ok;if(render)rows(unit,slot,&a,&b);}
}
static void api_boundaries(void)
{
    const unsigned units[]={3,0xffffffffu};const unsigned slots[]={0,9,0xffffffffu};
    KvRequest a,b;UvLevels v={{100}};unsigned i;
    for(i=0;i<2;++i){request(units[i],1,&v,-1,0);++api_rejected;}
    for(i=0;i<3;++i){request(0,slots[i],&v,-1,0);++api_rejected;}
    memset(&a,0xa5,sizeof(a));memset(&b,0xa5,sizeof(b));
    require(old_kv_data_request(&ov,0,1,NULL,&a)==-1,"old null levels");
    require(diag_kv_data_request(&dv,0,1,NULL,&b)==-1,"new null levels");
    require(!memcmp(&a,&b,sizeof(a)),"null output same");++api_rejected;
    require(old_kv_data_request(&ov,0,1,&v,NULL)==-1,"old null output");
    require(diag_kv_data_request(&dv,0,1,&v,NULL)==-1,"new null output");++api_rejected;
}
static void comparison_scope_check(void)
{
    KvRequest a,b;UvLevels levels={{100}};uint8_t changed[552],x[552],y[552];
    KvStats xs,ys;KvWork xw,yw;unsigned j;
    extern uint32_t gxr2_crc32(const uint8_t *,size_t);
    require(!old_kv_data_request(&ov,0,5,&levels,&a),"scope old request");
    require(!diag_kv_data_request(&dv,0,5,&levels,&b),"scope new request");
    require(!memcmp(&a,&b,sizeof(a)),"scope equal requests");
    memcpy(changed,fixtures[4],sizeof(changed));changed[115]^=1;
    uint32_t crc=gxr2_crc32(changed+115,96);
    for(j=0;j<4;++j)changed[16+j]=(uint8_t)(crc>>(24-8*j));
    require(!kv_apply_work(fixtures[3],fixtures[4],&a,x,&xs,&xw),"scope old output");
    require(!kv_apply_work(fixtures[3],changed,&b,y,&ys,&yw),"scope changed output");
    require(memcmp(x,y,sizeof(x))!=0,"final byte comparison detects changed base");
}
int main(int argc,char **argv)
{
    uint8_t old[17384],compact[7904],r2[7904],badpad[7904];
    KvDataView tmp;unsigned unit,slot,control,j,k;int raw_r3,raw_r2,tagged,diagnostic;
    require(argc==4,"arguments");read_file(argv[1],old,sizeof(old));
    read_file(argv[2],compact,sizeof(compact));read_file(argv[3],fixtures,sizeof(fixtures));
    require(old_kv_data_open(old,sizeof(old),&ov)==0,"old open");
    raw_r3=raw_kv_data_open(compact,sizeof(compact),&tmp);
    memcpy(r2,compact,sizeof(r2));r2[6]='2';
    /* Header CRC must match the changed tag. */
    extern uint32_t gxr2_crc_zeroed(const uint8_t *,size_t,size_t,size_t);
    uint32_t crc=gxr2_crc_zeroed(r2,sizeof(r2),16,4);
    for(j=0;j<4;++j)r2[16+j]=(uint8_t)(crc>>(24-8*j));
    raw_r2=raw_kv_data_open(r2,sizeof(r2),&tmp);
    tagged=r3_kv_data_open(compact,sizeof(compact),&tmp);
    diagnostic=diag_kv_data_open(compact,sizeof(compact),&dv);
    require(raw_r3==-1&&raw_r2==-1&&tagged==-1,"original format failures");
    require(diagnostic==0,"diagnostic open");
    memcpy(badpad,compact,sizeof(badpad));badpad[7903]=1;
    crc=gxr2_crc_zeroed(badpad,sizeof(badpad),16,4);
    for(j=0;j<4;++j)badpad[16+j]=(uint8_t)(crc>>(24-8*j));
    require(diag_kv_data_open(badpad,sizeof(badpad),&tmp)==-1,"nonzero pad rejected");
    for(unit=0;unit<3;++unit)for(slot=1;slot<=8;++slot){
        KvDataRecipe a,b;KvDataItem items[10];unsigned n;UvLevels base={{100}};
        static uint8_t membership[10][65536];
        memset(membership,0,sizeof(membership));
        require(!old_kv_data_recipe(&ov,unit,slot,&a),"old recipe");
        require(!diag_kv_data_recipe(&dv,unit,slot,&b),"new recipe");
        require(a.unit==b.unit&&a.slot==b.slot&&a.item_count==b.item_count&&a.first_item==b.first_item&&
                !memcmp(a.display,b.display,9),"recipe metadata");
        for(control=0;control<10;++control)membership[control][(uint16_t)base.v[control]]=1;
        n=a.item_count;
        for(j=0;j<n;++j){
            KvDataItem other;KvDataPoint x,y,unchanged;
            require(!old_kv_data_item(&ov,a.first_item+j,&items[j]),"old item");
            require(!diag_kv_data_item(&dv,b.first_item+j,&other),"new item");
            KvDataItem *item=&items[j];
            require(item->control==other.control&&item->point_count==other.point_count&&
                    item->cap_flags==other.cap_flags&&item->amount_step==other.amount_step&&
                    item->min_level==other.min_level&&item->max_level==other.max_level&&
                    item->default_level==other.default_level,"item metadata");
            memset(membership[item->control],0,65536);
            for(k=0;k<item->point_count;++k){char text1[9],text2[9];
                require(!old_kv_data_point(&ov,item,k,&x),"old point");
                require(!diag_kv_data_point(&dv,&other,k,&y),"new point");
                require(x.level==y.level&&x.dose==y.dose,"point pair");
                membership[item->control][(uint16_t)x.level]=1;
                memset(text1,0xa5,sizeof(text1));memset(text2,0xa5,sizeof(text2));
                require(!old_kv_ui_value(&ov,unit,slot,item->control,x.level,text1),"old value text");
                require(!diag_kv_ui_value(&dv,unit,slot,item->control,x.level,text2),"new value text");
                require(!memcmp(text1,text2,sizeof(text1)),"value text bytes");++text_cases;
            }
            memset(&x,0xa5,sizeof(x));memset(&y,0xa5,sizeof(y));memset(&unchanged,0xa5,sizeof(unchanged));
            require(old_kv_data_point(&ov,item,item->point_count,&x)==-1,"old point end");
            require(diag_kv_data_point(&dv,&other,other.point_count,&y)==-1,"new point end");
            require(!memcmp(&x,&unchanged,sizeof(x))&&!memcmp(&y,&unchanged,sizeof(y)),"point rejection unchanged");
            ++index_rejected;
        }
        request(unit,slot,&base,0,1);
        for(control=0;control<10;++control)for(int value=-32768;value<=32767;++value){
            UvLevels v=base;v.v[control]=(int16_t)value;
            request(unit,slot,&v,membership[control][(uint16_t)value]?0:-1,1);
        }
        for(j=0;j<n;++j)for(k=j+1;k<n;++k)for(unsigned choice=0;choice<4;++choice){
            KvDataPoint x,y;UvLevels v=base;
            require(!old_kv_data_point(&ov,&items[j],(choice&1)?items[j].point_count-1u:0u,&x),"pair left");
            require(!old_kv_data_point(&ov,&items[k],(choice&2)?items[k].point_count-1u:0u,&y),"pair right");
            v.v[items[j].control]=x.level;v.v[items[k].control]=y.level;
            request(unit,slot,&v,0,1);++pair_cases;
        }
        for(unsigned choice=0;choice<2;++choice){UvLevels v=base;
            for(j=0;j<n;++j){KvDataPoint p;require(!old_kv_data_point(&ov,&items[j],choice?items[j].point_count-1u:0u,&p),"all extrema");v.v[items[j].control]=p.level;}
            request(unit,slot,&v,0,1);
        }
    }
    api_boundaries();comparison_scope_check();
    printf("{\"old_open\":0,\"raw_r3_open\":%d,\"raw_r2_open\":%d,\"r3_tag_only_open\":%d,\"diagnostic_open\":%d,"
           "\"int16_single_control_cases\":15728640,\"request_cases\":%llu,\"request_ok\":%llu,\"request_rejected\":%llu,"
           "\"final_552_cases\":%llu,\"final_552_ok\":%llu,\"final_552_rejected_unchanged\":%llu,"
           "\"pair_extrema_cases\":%llu,\"text_cases\":%llu,\"point_index_rejections\":%llu,\"api_boundary_rejections\":%llu,"
           "\"equal_request_changed_base_detected_by_final_bytes\":true}\n",
           raw_r3,raw_r2,tagged,diagnostic,request_cases,request_ok,request_rejected,
           row_cases,row_ok,row_rejected,pair_cases,text_cases,index_rejected,api_rejected);
    return 0;
}
