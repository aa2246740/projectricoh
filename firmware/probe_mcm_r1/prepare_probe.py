"""Copy the proven constructor seed, then narrow this DAT's services."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import probe_common as c


def main():
    c.guard()
    for name in ('resident.h', 'abi.h', 'gxrce.h', 'shared.c'):
        c.output(c.HERE / 'resident' / name).write_bytes((c.ROOT / 'firmware/resident_v36/resident' / name).read_bytes())
    for name in ('api.c', 'services.c', 'runtime.c', 'crc.c', 'native_seed.c', 'engine_services.h', 'bridges.S'):
        source = c.ROOT / 'firmware/engine_v38_b36/candidate/engine_services' / name
        destination=c.output(c.HERE / 'services' / name)
        destination.write_text(source.read_text().replace('../../resident/resident.h','../resident/resident.h'))
    for name in ('kernel.c', 'kernel.h', 'vectors.py', 'entry.S', 'engine.ld'):
        c.output(c.HERE / name).write_bytes((c.ROOT / 'firmware/lut_p0_timing' / name).read_bytes())
    path = c.HERE / 'services/services.c'
    text = path.read_text()
    begin, end = text.index('static int file_buffer('), text.index('static RvUiSnapshot *ui_prepare(')
    text = text[:begin] + text[end:]
    begin, end = text.index('static int32_t settings('), text.index('int32_t rv_service(')
    text = text[:begin] + text[end:]
    text = text.replace('int32_t es_storage_mark(RvRoot *,const RvRequest *,RvReply *);', '')
    old = 'if(id==RV_STORAGE){if((r->flags&RF_OWNER)){result=RV_BUSY;goto finish;}r->flags|=RF_OWNER;result=storage(r,op,q,p);r->flags&=~RF_OWNER;goto finish;}'
    assert old in text
    text = text.replace(old, 'if(id==RV_STORAGE||id==RV_PREVIEW||id==RV_SETTINGS||id==RV_CACHE){result=RV_CAPABILITY;goto finish;}')
    text = text.replace('u->rows<1||u->rows>16','u->rows!=8')
    text = text.replace('||!a||a>73728u', '||!a||a>RV_MAX_LEASE')
    begin, end = text.index('    case RV_PREVIEW:\n', text.index('    r->flags|=RF_OWNER;')), text.index('    case RV_UNIT:\n', text.index('    r->flags|=RF_OWNER;'))
    text = text[:begin] + text[end:]
    begin, end = text.index('        if(op==3&&(r->state'), text.index('p->native_result=result;', text.index('        if(op==3&&(r->state'))
    text = text[:begin] + '''        if(op==3){result=RV_CAPABILITY;break;}
        if(op==4&&a!=0x2012&&a!=0x2014&&a!=0x2038){result=RV_RANGE;break;}
        result=rv_rpc8_native(op==2?21:23,a);''' + text[end:]
    text = text.replace('if(op==3&&(uint32_t)result!=a)', 'if(op==3&&(uint32_t)result!=a)')
    # Both capture sites call exactly the same authoritative condition under IRQ.
    guard = (c.HERE / 'p1_guard.inc.c').read_text()
    text = text.replace('static RvUiSnapshot *ui_prepare(', guard + '\nstatic RvUiSnapshot *ui_prepare(', 1)
    text = text.replace('static int32_t ui_list(RvRoot *r,uint32_t op,RvUiList *u)', 'static int32_t ui_list(RvRoot *r,uint32_t op,RvUiList *u,const RvRequest *q)')
    text = text.replace('static int32_t ui_view(RvRoot *r,uint32_t op,RvUiView *u)', 'static int32_t ui_view(RvRoot *r,uint32_t op,RvUiView *u,const RvRequest *q)')
    old = 'if(!rv_ui_capture(r)){rv_irq_restore(irq);return RV_STALE;}'
    new = 'if(!probe_p1_capture(r,q,u->lease_token,u->state_address,u->state_bytes)){rv_irq_restore(irq);return RV_CONFLICT;}'
    assert text.count(old) == 2
    text = text.replace(old, new).replace('ui_list(r,op,u):RV_ARGUMENT', 'ui_list(r,op,u,q):RV_ARGUMENT').replace('ui_view(r,op,buffer);', 'ui_view(r,op,buffer,q);')
    # UI_VIEW must revalidate the exact destination slot after allocation.
    begin=text.index('static int32_t ui_view(')
    before,view=text[:begin],text[begin:]
    view=view.replace('    irq=rv_irq_save();\n', '''    irq=rv_irq_save();
    array=RV_WORD(0x205a27d8);count=RV_BYTE(0x205a27d4);
    if(array!=u->expected_array||array!=RV_NATIVE_VIEWS||count!=u->expected_count||!count||count>2){rv_irq_restore(irq);return RV_CONFLICT;}
    top=array+8*(count-1);
    if(RV_BYTE(top)!=33||RV_BYTE(top)!=u->expected_top_tag||RV_WORD(top+4)!=u->expected_top_state){rv_irq_restore(irq);return RV_CONFLICT;}
''',1)
    text=before+view
    old='if(id==RV_UI_TEXT&&op==2){p->detail=rv_native_language();result=RV_OK;}'
    new='''if(id==RV_UI_TEXT&&op==2){
            p->detail=rv_native_language();a=RV_BYTE(0x2023eab8);
            if((a==10?1:a)!=p->detail){result=RV_STALE;}
            else{s->ui_lengths[14]=a;s->ui_lengths[15]=0x4c414e47u;result=RV_OK;}
        }'''
    assert old in text
    text=text.replace(old,new)
    text=text.replace('            p->native_result=rv_native_ascii(', '''            if(s->ui_lengths[15]!=0x4c414e47u||s->ui_lengths[14]!=RV_BYTE(0x2023eab8)||
               u->language!=(s->ui_lengths[14]==10?1:s->ui_lengths[14])){result=RV_STALE;break;}
            p->native_result=rv_native_ascii(''')
    text=text.replace('            if(!current(r,q)){result=RV_STALE;break;}\n            for(i=0;i<u->glyph_capacity',
        '            if(!current(r,q)||s->ui_lengths[14]!=RV_BYTE(0x2023eab8)){result=RV_STALE;break;}\n            for(i=0;i<u->glyph_capacity')
    path.write_text(text)
    path=c.HERE/'services/api.c'
    text=path.read_text().replace('D(1,0x3fe)','D(1,0)').replace('D(3,2)','D(3,0)').replace('D(4,62)','D(4,54)').replace('D(5,2)','D(5,0)').replace('D(6,14)','D(6,0)')
    path.write_text(text)
    path = c.HERE / 'resident/shared.c'
    text = path.read_text()
    text = text.replace('if(v[10]<1||v[10]>7)v[10]=1;\n        if(v[11]<1||v[11]>7)v[11]=1;', '/* probe_p1_capture atomically validated both raw bytes. */')
    path.write_text(text)
    path = c.HERE / 'services/bridges.S'
    text = path.read_text()
    forbidden = ('rv_native_open', 'rv_native_read', 'rv_native_close', 'rv_native_create', 'rv_native_write', 'rv_native_rename', 'rv_native_delete', 'rv_native_preview')
    text = '\n'.join(line for line in text.splitlines() if not any('NATIVE ' + name + ',' in line for name in forbidden)) + '\n'
    path.write_text(text)
    c.save(c.LOCAL / 'service-changes.json', dict(storage='entire class rejected', rpc='X/V only; W rejected',
        capture_sites=2, seed_source='engine_v38_b36/candidate', resident_binding=str(c.TRUST), deleted_bridges=forbidden))


if __name__ == '__main__':
    main()
