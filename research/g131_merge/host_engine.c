/* Host entry points using the integrated engine's real data and compute path. */
#include "eng_core.c"

int eng_settings_owned(void){return 1;}
uint32_t eng_wire_address(const void *p){return (uint32_t)(uintptr_t)p;}
void *eng_wire_pointer(uint32_t address){return (void *)(uintptr_t)address;}

static int32_t host_service(void *user,uint32_t service,uint32_t op,uint32_t a,uint32_t b,
                            void *buffer,uint32_t bytes,uint32_t count,RvReply *reply)
{
    unsigned i,unit=*(unsigned *)user;(void)op;(void)a;(void)b;(void)bytes;(void)count;
    static const uint8_t names[3][8]={"jlaunch","qlaunch","l08firm"};
    ig_zero(reply,sizeof(*reply));reply->version=1;reply->bytes=sizeof(*reply);
    if(service==RV_EPOCHS){
        RvEpochSnapshot *value=buffer;ig_zero(value,sizeof(*value));
        value->header.version=1;value->header.bytes=sizeof(*value);
        for(i=0;i<8;++i)value->epochs[i]=1;
    }else if(service==RV_UNIT){
        RvUnitInfo *value=buffer;ig_zero(value,sizeof(*value));
        value->header.version=1;value->header.bytes=sizeof(*value);
        value->valid=1;value->main_version=0x151;value->unit_epoch=1;value->link_epoch=1;
        ig_copy(value->name,names[unit],8);
    }else{reply->status=RV_UNAVAILABLE;return RV_UNAVAILABLE;}
    reply->status=RV_OK;return RV_OK;
}

int g131_open(const uint8_t *dat,unsigned length,unsigned unit)
{
    Gxr2Trust trust;Gxr2View gate;Gxr2Unit identity;EngPort port;unsigned i;static unsigned selected;
    if(unit>=3)return -1;selected=unit;eng_host_reset();
    ig_zero(&trust,sizeof(trust));ig_zero(&identity,sizeof(identity));ig_zero(&port,sizeof(port));
    ig_copy(trust.body_sha256,dat+48,32);ig_copy(trust.resident_build_id,dat+80,32);
    ig_copy(trust.resident_abi_id,dat+212,16);
    for(i=0;i<3;++i){uint32_t pin=rv_unit_pin((uint8_t)i);uint8_t *p=trust.modules[i].stock_sha256;
        static const uint8_t names[3][8]={"jlaunch","qlaunch","l08firm"};
        ig_copy(trust.modules[i].unit.name,names[i],8);trust.modules[i].unit.main_version=0x151;
        trust.modules[i].stock_crc32=pin;p[0]=pin>>24;p[1]=pin>>16;p[2]=pin>>8;p[3]=pin;
    }
    identity=trust.modules[unit].unit;
    if(gxr2_gate_validate(dat,length,&trust,&identity,0,&gate)!=GXR2_OK)return -2;
    port.call=host_service;port.user=&selected;port.gated=&gate;
    {EngStatus status=eng_init(dat,length,&port);return status==ENG_OK?eng_menu_open():status;}
}

int g131_compute(unsigned slot,const UvLevels *levels,uint8_t out[552])
{return eng_project_compute(slot,levels,out);}

#ifndef G131_REFERENCE
int g131_request(unsigned slot,const UvLevels *levels,KvRequest *out)
{return kv_data_request(&g.data.knobs,g.data.unit,slot,levels,out);}

int g131_invalid_preview(unsigned slot)
{UvLevels levels={{100}};return eng_project_preview(slot,&levels);}

int g131_golden(const uint8_t stock[552],const uint8_t base[552],const KvRequest *request,
                 uint8_t out[552],KvStats *stats)
{KvWork work;return kv_apply_work(stock,base,request,out,stats,&work);}

int g131_default(unsigned slot,UvLevels *levels)
{return kv_ui_default(&g.data.knobs,g.data.unit,slot,levels);}

int g131_ui(const KvUiModel *model,const KvUiNav *nav,KvUiFrame *frame)
{return kv_ui_render(&g.data.knobs,model,nav,frame);}

int g131_plan(unsigned slot,const UvLevels *levels,uint32_t token,RvSettingsPlan *plan)
{
    EngRecipeRef ref;uint8_t wb[2];EngStatus status;
    ref.unit=g.data.unit;ref.slot=slot;eng_identity(eng_record(&g.data,slot),ref.identity);
    status=compute(&ref,levels,wb);if(status!=ENG_OK)return status;
    make_plan(&ref,wb,token,plan);return ENG_OK;
}
#else
int g127_default(unsigned slot,uint32_t token,RvSettingsPlan *plan,uint8_t out[552])
{
    EngRecipeRef ref;EngTweak levels={{0}};uint8_t wb[2];EngStatus status;
    ref.unit=g.data.unit;ref.slot=slot;eng_identity(eng_record(&g.data,slot),ref.identity);
    status=compute(&ref,&levels,wb);if(status!=ENG_OK)return status;
    make_plan(&ref,wb,token,plan);ig_copy(out,g.staging,552);return ENG_OK;
}
#endif
