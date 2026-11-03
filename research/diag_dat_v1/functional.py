"""Run pages and native keys against the final compiled DAT on all three units."""
from pathlib import Path
import argparse
import json
import sys
import traceback
sys.path.insert(0,str(Path(__file__).resolve().parent))
from trace import *


def assert_page(h,p,page,seq):
    s=snapshot(h,p)
    assert s['rows']==8 and s['text'][0][0]==page and s['opens']==seq,s
    assert len(s['text'])==8 and all(0<len(row)<=8 and row.isascii() for row in s['text']),s
    assert s['cursor']==s['marker']==s['cache']==1,s
    at=symbol(p,'n')+N_OFFSETS['sample']
    values={key:h.u(at+4*i) for i,key in enumerate(LAYOUT['field_order'])}
    expected=[f'{page}{seq&65535:04X} '+('C' if private(h,p,'changed',1) else 'S')]
    for row in LAYOUT['pages'][page]:
        expected.append(''.join(f'{seq>>16:04X}' if f=='open_high' else
            f'{values[f]:0{LAYOUT["fields"][f][1]*2}X}' for f in row))
    assert s['text']==expected,(s['text'],expected)
    ui=s['root']['ui_restore6']-296
    for i in range(8):
        ref=h.u(s['root']['ui_restore6']+4*i)
        glyph=h.u(ref)
        assert ref==ui+360+4*i and glyph==ui+424+96*i
        private_glyph=symbol(p,'n')+N_OFFSETS['glyphs']+70*i
        assert h.b.read(glyph,70).split(b'\0',1)[0]==h.b.read(private_glyph,70).split(b'\0',1)[0]
    return s


def run(unit):
    h,p,w,arm=setup(unit);audit=Audit(h,p,arm)
    report=dict(unit=unit,pages=[],events=[])
    try:
        report['opened']=open_menu(h,p)
        saved=h.b.read(symbol(p,'n')+N_OFFSETS['sample'],200)
        for page in 'ABCDF':
            if page!='A':report['events'].append(action(h,p,'disp'))
            report['pages'].append(assert_page(h,p,page,1))
            assert h.b.read(symbol(p,'n')+N_OFFSETS['sample'],200)==saved
        action(h,p,'disp');assert_page(h,p,'A',1)
        for name in ('up','down','up','down'):
            report['events'].append(action(h,p,name));assert_page(h,p,'A',1)
        assert len(audit.captures)==1,audit.captures
        for seq,name in enumerate(('ok','adj','half'),2):
            report['events'].append(dict(action=name,result=action(h,p,name),after=snapshot(h,p)))
            assert h.u(0x2037f3bc)==0,snapshot(h,p)
            if name!='half':assert h.u(0x2022f5ac,1)==7,snapshot(h,p)
            else:
                # The native shutter can hide ADJ without H07. Preserve the
                # eight-row publication until the next legal constructor.
                assert h.u(0x2022f5ac,1) in (7,8),snapshot(h,p)
            open_menu(h,p);assert_page(h,p,'A',seq)
        for capture in audit.captures:
            keys=LAYOUT['field_order']
            assert [e['field'] for e in capture]==keys+keys,len(capture)
        report['audit']=audit.result()
        assert report['audit']['settings_unchanged']
        report['final']=snapshot(h,p);report['status']='PASS'
    except BaseException:
        report.update(status='FAIL',error=traceback.format_exc(),audit=audit.result(False),after=snapshot(h,p))
        raise
    finally:
        save(OUT/'local/functional'/f'{unit}.json',report)
        print(unit,report['status'],report.get('error','')[-1000:],flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--unit',choices=('50mm','28mm','mount'),required=True)
    run(parser.parse_args().unit)
