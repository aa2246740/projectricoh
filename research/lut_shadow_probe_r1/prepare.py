"""Freeze existing inputs and copy firmware-derived dependencies into local only."""
from pathlib import Path
import json
import re
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import common as C

def main():
    C.setup()
    dst=C.ENGINE/'local/dependencies'
    assert not dst.exists(), 'one-time preparation; preserve existing local source'
    for part in ('resident','engine_services'): (dst/part).mkdir(parents=True)
    files=[]
    for name in ('resident.h','abi.h','gxrce.h','shared.c'):
        source=C.BASE/'resident'/name
        (dst/'resident'/name).write_bytes(source.read_bytes()); files.append(source)
    for name in ('engine_services.h','api.c','runtime.c','native_seed.c','bridges.S','settings_record.h'):
        source=C.BASE/'candidate/engine_services'/name
        (dst/'engine_services'/name).write_text(source.read_text().replace('../../resident/','../resident/')); files.append(source)
    service=C.BASE/'candidate/engine_services/services.c'; files.append(service)
    s=service.read_text()
    definitions=s[s.index('static int header('):s.index('static int32_t free_session_work(')]
    start=definitions.index('static uint32_t token('); end=definitions.index('static int identity(',start)
    definitions=definitions[:start]+definitions[end:]
    ui=s[s.index('static RvUiSnapshot *ui_prepare('):s.index('static int32_t ui_view(')]
    tail='''
int32_t rv_service(RvRoot *r,uint32_t id,uint32_t op,const RvRequest *q,RvReply *p)
{
    RvSession *s=rv_session(r);uint32_t bytes,i;void *buffer;int32_t result=RV_UNSUPPORTED;
    if(!q||!p||((uintptr_t)q&3)||((uintptr_t)p&3))return RV_ARGUMENT;
    rv_clear(p,32);p->version=1;p->bytes=32;
    if(q->version!=1||q->bytes!=64||q->flags){result=RV_ARGUMENT;goto finish;}
    if(id!=RV_UI_LIST&&id!=RV_UI_TEXT){result=RV_CAPABILITY;goto finish;}
    if(!current(r,q)){result=RV_STALE;goto finish;}
    if(!r->inflight||rv_native_context()!=0){result=RV_OWNER;goto finish;}
    if(r->flags&RF_OWNER){result=RV_BUSY;goto finish;}
    if(r->state!=RV_READY||!s||!(s->capabilities&CAP_UI)){result=RV_CAPABILITY;goto finish;}
    bytes=q->args[11];buffer=RV_PTR(q->args[10]);
    if(q->args[8]||q->args[13]){result=RV_ARGUMENT;goto finish;}
    if(id==RV_UI_TEXT&&(q->args[9]||q->args[12])){result=RV_ARGUMENT;goto finish;}
    if(bytes&&(!rv_range(r,q->args[1],q->args[10],bytes)||(q->args[10]&3)||!header(buffer,bytes))){result=RV_RANGE;goto finish;}
    if(!bytes&&q->args[10]){result=RV_ARGUMENT;goto finish;}
    r->flags|=RF_OWNER;
    if(id==RV_UI_TEXT&&op==2&&!bytes){p->detail=rv_native_language();result=RV_OK;}
    if(id==RV_UI_TEXT&&op==1&&bytes==40){
        RvUiText *u=buffer;
        if(!u->source_bytes||u->source_bytes>39||u->glyph_capacity<2*u->source_bytes+1||
           !rv_range(r,u->source_lease,u->source_address,u->source_bytes+1)||
           !rv_range(r,u->glyph_lease,u->glyph_address,u->glyph_capacity)){result=RV_RANGE;goto release;}
        for(i=0;i<u->source_bytes;++i)if(RV_BYTE(u->source_address+i)<32||RV_BYTE(u->source_address+i)>126)break;
        if(i!=u->source_bytes||RV_BYTE(u->source_address+i)){result=RV_ARGUMENT;goto release;}
        p->native_result=rv_native_ascii(RV_PTR(u->source_address),u->source_bytes,RV_PTR(u->glyph_address),u->language);
        if(!current(r,q)){result=RV_STALE;goto release;}
        result=RV_OK;
        for(i=0;i<u->glyph_capacity&&RV_BYTE(u->glyph_address+i);++i){}
        if(i==u->glyph_capacity)result=RV_VERIFY;
        else {u->actual_bytes=i;p->actual=40;}
    }
    if(id==RV_UI_LIST&&op>=1&&op<=3&&bytes==40){
        RvUiList *u=buffer;
        if(u->rows!=8||q->args[9]!=8||q->args[12]!=8)result=RV_ARGUMENT;
        else {result=ui_list(r,op,u);if(!result){p->token=u->view_token;p->epoch=r->epoch[RV_VIEW_E];}}
    }
release:r->flags&=~RF_OWNER;
finish:p->status=result;return result;
}
'''
    (dst/'engine_services/services.c').write_text('#include "engine_services.h"\n'+definitions+ui+tail)
    api=dst/'engine_services/api.c'; s=api.read_text()
    s=s[:s.index('#define D(i,m)')]+'''#define D(i,m) {i,64,m}
const RvApi rv_api={1,sizeof(RvApi),16,RV_READ_CAPS,256,rv_call,{0},
 {D(1,0),D(2,0),D(3,0),D(4,0),D(5,0),D(6,0),D(7,0),D(8,0),
  D(9,0),D(10,14),D(11,6),D(12,0),D(13,0),D(14,0),D(15,0),D(16,0)}};
'''; api.write_text(s)
    # Only UI helpers, allocator and identity/context reads survive in this profile.
    bridges=dst/'engine_services/bridges.S'; s=bridges.read_text()
    allow={'rv_native_alloc','rv_native_free','rv_native_ascii','rv_native_language','rv_native_draw',
           'rv_native_context','rv_native_rpc_ready'}
    s='\n'.join(line for line in s.splitlines() if not re.match(r'\s*NATIVE\s+rv_',line) or re.search(r'NATIVE\s+(\w+),',line).group(1) in allow)+'\n'
    start=s.index('    .balign 4\n    .global rv_rpc8_native'); end=s.index('    .balign 4\n    .global rv_irq_save',start)
    s=s[:start]+s[end:]; bridges.write_text(s)
    timing=C.ROOT/'firmware/probe_mcm_r1/timing.S'; files.append(timing)
    s=timing.read_text(); s=s[:s.index('    .balign 4\n    .global p0_empty')]+s[s.index('    .balign 4\n    .global p0_irq_enabled'):s.index('    .balign 4\n    .global p0_decrement')]
    (C.ENGINE/'local/timing.S').write_text(s.replace('p0_tick','lp_tick').replace('p0_irq_enabled','lp_irq_enabled'))
    files += [C.BODY,C.RESIDENT/'local/resident/resident.elf',C.BASE/'resident/loader.c',C.BASE/'resident/hooks.c',C.BASE/'resident/validate_envelope.inc.c']
    for folder in (C.BASE/'candidate/containers/product',):
        files += [folder/n for n in ('adapter.c','engine.ld')]
    files += [C.ROOT/'research'/p/'REPORT.md' for p in ('v311_feasibility_r1','body_lut_r2','cpu_speed_r1','look_ceiling_r1')]
    receipt={str(p.relative_to(C.ROOT)):dict(sha256=C.sha(p.read_bytes()),bytes=p.stat().st_size) for p in files}
    assert C.sha(C.BODY.read_bytes()).startswith('a04f1ed4'), 'wrong current body'
    C.save(C.LOCAL/'protected-inputs.json',receipt)
    C.save(C.LOCAL/'prepared.json',dict(generation=C.GENERATION,source_files=len(files),dependency_profile='UI list/text only; capture has no service calls'))
    print(json.dumps(dict(status='PREPARED',generation=C.GENERATION,files=len(files))))

if __name__=='__main__': main()
