"""Execute final M32R range and virtual-window functions on an officially constructed session."""
from pathlib import Path
import argparse
import struct
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from ui_test_support import *
from common import run

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--unit',default='50mm',choices=('50mm','28mm','mount'))
    args=parser.parse_args();s=Session(args.unit,'project-boundary')
    folder=OUT/'local/layout';folder.mkdir(exist_ok=True)
    source=folder/('gate-offset-'+args.unit+'.c');obj=folder/('gate-offset-'+args.unit+'.o')
    source.write_text('#define ENG_HOST 1\n#include "'+str(TREE/'candidate/containers/product/adapter.c')+'"\n'
                      'const unsigned offset __attribute__((section(".layout"),used))=offsetof(Integrated,gate);\n')
    run([ROOT/'research/tooling_m32r_c/prefix/gcc/bin/m32r-elf-gcc','-std=c11','-Os','-ffreestanding','-fno-builtin',
         '-m32r','-msdata=none','-G0','-DPN_CORE_HEADER="../core/eng_core.h"','-DPN_GXTS_SHARED_PARAMETER',
         '-DACCEPTANCE_ENTRIES_HEADER="'+str(TREE/'candidate/local/product-r13/entries.h')+'"','-c',source,'-o',obj], 'gate-offset-'+args.unit)
    reader=load(ROOT/'tools/native_harness/image_loader.py','gate_offset_elf')
    raw=next(sec['data'] for sec in reader.Elf(obj).sections if sec['name']=='.layout')
    gate=s.adapter+int.from_bytes(raw,'big')
    scratch=0x20660000;s.h.b.map(scratch,bytes(4096));out=scratch+64
    levels_pc=s.p.symbol_pc('uv_levels');window_pc=s.p.symbol_pc('uv_window')
    checks=[];at=len(s.p.rpc.log);before=s.state()
    for base in range(1,9):
        for param in range(11):
            for value in range(-9,10):
                levels=[0]*11;levels[param]=value
                s.h.b.write(scratch,struct.pack('11b',*levels));s.h.b.write(out,b'\x55'*8)
                result=s.ux.need(s.p.call(levels_pc,(gate,base,scratch,out),steps=10000))
                expected=(abs(value)<=5) if param<4 else value==0
                if base==3 and param==3:expected=value==0
                assert bool(result['r0'])==expected,(base,param,value,result)
                if expected:
                    legacy=[0]*8
                    if param<4:legacy[(0,2,3,1)[param]]=value
                    assert s.h.b.read(out,8)==struct.pack('8b',*legacy)
                checks.append(dict(base=base,param=param,value=value,accepted=expected))
        for sign in (-1,1):
            levels=[5*sign,-5*sign,5*sign,0 if base==3 else -5*sign]+[0]*7
            s.h.b.write(scratch,struct.pack('11b',*levels))
            result=s.ux.need(s.p.call(levels_pc,(gate,base,scratch,out),steps=10000))
            assert result['r0']==1
            expected=[levels[0],levels[3],levels[1],levels[2],0,0,0,0]
            assert s.h.b.read(out,8)==struct.pack('8b',*expected)
            checks.append(dict(base=base,combined_levels=levels,accepted=True))
    s.h.b.write(scratch,bytes(11))
    for base in (0,9,16,255):
        s.h.b.write(out,b'\x55'*8)
        result=s.ux.need(s.p.call(levels_pc,(gate,base,scratch,out),steps=10000))
        assert not result['r0'] and s.h.b.read(out,8)==b'\x55'*8
        checks.append(dict(base=base,accepted=False))
    levels=[0]*11;levels[10]=-10;s.h.b.write(scratch,struct.pack('11b',*levels))
    result=s.ux.need(s.p.call(levels_pc,(gate,5,scratch,out),steps=10000))
    assert not result['r0']
    checks.append(dict(base=5,param=10,value=-10,accepted=False))
    windows=0
    for count in range(1,34):
        for cursor in range(count):
            for old_top in range(max(1,count-7)):
                result=s.ux.need(s.p.call(window_pc,(count,cursor,old_top,out),steps=3000))
                top,physical=s.h.b.read(out,2)
                assert 0<=physical<8 and top+physical==cursor and top<=max(0,count-8),(count,cursor,old_top,top,physical)
                if count>8 and cursor>0 and top>0:assert physical>0
                if count>8 and cursor<count-1 and top+8<count:assert physical<7
                windows+=1
    assert len(s.p.rpc.log)==at and s.state()==before,'pure range/window functions changed native or engine UI'
    save('evidence/project-boundary-'+args.unit+'.json',dict(status='PASS',dat_sha256=sha(s.p.dat),
         actual_M32R=True,official_constructor=True,native_UI_hand_seeded=False,
         level_cases=len(checks),levels=checks,window_cases=windows,virtual_row_counts=list(range(1,34)),
         virtual_19_rows=True,physical_rows=8,range_rejections_proven=True,extra_RPC=0,native_UI=ui_audit(s.h)))
    print('PASS',args.unit,len(checks),'M32R range cases;',windows,'M32R windows including 19 virtual rows')

if __name__=='__main__':main()
