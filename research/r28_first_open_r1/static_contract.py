"""Check the source boundaries that constrain a package-only change."""
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ROOT, save, sha, verify_pins
sys.path.insert(0, str(ROOT / 'tools/native_harness'))
from image_loader import Elf


def anchor(path, first, last=None):
    raw = (ROOT / path).read_bytes()
    text = raw.decode()
    begin = text.index(first)
    end = text.index(last, begin)+len(last) if last else begin+len(first)
    return dict(path=path, sha256=sha(raw), first_line=text.count('\n', 0, begin)+1,
                last_line=text.count('\n', 0, end)+1)


def run():
    verify_pins()
    hpath = 'firmware/resident_v36/resident/hooks.c'
    lpath = 'firmware/resident_v36/resident/loader.c'
    rpath = 'firmware/resident_v36/resident/resident.c'
    spath = 'firmware/engine_v42_ux/candidate/engine_services/services.c'
    npath = 'firmware/engine_v42_ux/candidate/engine_services/native_seed.c'
    apath = 'firmware/engine_v42_ux/candidate/containers/product/adapter.c'
    hooks, loader, resident, services, seed, adapter = [(ROOT/p).read_text()
                                                     for p in (hpath, lpath, rpath, spath, npath, apath)]
    observer = hooks[hooks.index('void rv_hook_observe'):]
    h9 = observer[observer.index('if(hook==9)'):observer.index('if(hook==5)')]
    h5 = observer[observer.index('if(hook==5)'):observer.index('if(r->magic!=')]
    assert 'return;' in h5 and 'return;' in h9
    assert all(word not in h5+h9 for word in ('rv_load(', 'rv_engine('))
    assert hooks.count('rv_load(') == 1
    assert 'if(hook==1){\n        if(r->state!=RV_READY&&rv_load(r,&rv_trust))return;' in hooks
    assert '}else if(!owned(r,hook))' in hooks
    readiness = loader.index('if(!ready)return RV_STALE;')
    attempted = loader.index('r->flags|=RF_ATTEMPTED|RF_BUSY;')
    first_open = loader.index('status=rv_native_open(sources[2],0);')
    assert readiness < attempted < first_open
    assert 'rv_engine(' not in resident[resident.index('void rv_grain('):]
    assert 'if(op==3&&!rv_view_owned(r,u,0))' in services
    assert 'if(r->state!=RV_READY||!(s->capabilities&CAP_UI))' in services
    assert 'if(!r->inflight||rv_native_context()!=0)' in services
    assert 'if(!v' not in h9
    event_block = services[services.index('    case RV_EVENTS:\n        if(op==2)'):services.index('    case RV_QUERY:\n        if(op==2')]
    assert 'rv_record(' in event_block and 'u->events' in event_block
    assert not any(word in event_block for word in ('rv_engine(', 'rv_load(', 'rv_native_draw('))
    assert 'RV_WORD(0x2022f5a8)!=s->list||RV_BYTE(0x2022f5ac)!=s->rows' in seed
    assert 'if(operation==3&&!view_owned())' in adapter
    symbols = Elf(ROOT/'firmware/resident_v36/local/resident/build/resident.elf').symbols
    code_end = symbols['__resident_code_end']
    assert code_end == 0x20054638
    result = dict(status='PASS', resident_end=hex(code_end), reserved_bytes=0x20054700-code_end,
                  available_with_200_byte_reserve=0x20054700-200-code_end,
                  source_anchors={
                      'H05_and_H09': anchor(hpath, 'if(hook==9)', 'if(r->magic!='),
                      'H01_only_load': anchor(hpath, 'if(hook==1){', 's=rv_session(r);'),
                      'ready_before_file_access': anchor(lpath, 'if(!trust)', 'status=rv_native_open(sources[2],0);'),
                      'grain_only': anchor(rpath, 'void rv_grain('),
                      'op3_active_list_guard': anchor(spath, 'if(op==3&&!rv_view_owned', 'if(op==3){s->redraw=1;'),
                      'UI_service_ready_guard': anchor(spath, '    case RV_UI_LIST:case RV_UI_VIEW:case RV_UI_TEXT:', 'if(id==RV_UI_VIEW&&bytes==48)'),
                      'event_snapshot': anchor(spath, '    case RV_EVENTS:\n        if(op==2)', '    case RV_QUERY:\n        if(op==2'),
                      'view_ownership': anchor(npath, 'int __attribute__((noinline)) rv_view_owned', 'int32_t rv_native_seed'),
                      'list_binding': anchor(apath, 'static int32_t list_bind(', 'static int preload_gxts'),
                      'engine_menu_entry': anchor(apath, 'int32_t ig_menu(', 'int32_t ig_apply('),
                      'ASCII_text': anchor(spath, 'if(id==RV_UI_TEXT&&op==1', '    case RV_EVENTS:'),
                  },
                  hooks_without_engine_or_load=[5, 9],
                  load_hook=1,
                  file_access_after_ready_gate=True,
                  events_service='read ring records or append a record; no callback registration',
                  generation120_status=(ROOT/'firmware/engine_v42_ux/STATUS.txt').read_text().strip(),
                  generation120_code_executed=False)
    save('static-contract.json', result)
    print(json.dumps(dict(status='PASS', source_anchors=len(result['source_anchors']),
                          reserve=result['reserved_bytes'], headroom=result['available_with_200_byte_reserve'])))


if __name__ == '__main__':
    run()
