#!/usr/bin/env python3
"""Run actual production C under both sanitizers. No camera/card I/O."""
import json
import os
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from runtime import HERE,ROOT,LOCAL,guard,load,run,sha

def main():
    guard();load(HERE/'fixture.py','local_fixture').build()
    sources=[HERE/'test_host.c',HERE/'eng_data.c',HERE/'eng_crc_compat.c',HERE/'eng_semantic.c',HERE/'eng_pin_stub.c',ROOT/'firmware/card_container_v2/common.c',HERE/'eng_core.c',HERE/'eng_grain.c',HERE/'eng_entries.c',ROOT/'research/recipe_tweak/r2/tweak_int.c',ROOT/'firmware/card_container_v2/gate.c']
    flags=['-std=c11','-O1','-g','-Wall','-Wextra','-Werror','-DENG_HOST','-fsanitize=address,undefined','-fno-sanitize-recover=all','-fno-omit-frame-pointer']
    binary=LOCAL/'test-host';run(['clang',*flags,*sources,'-o',binary],'host-compile')
    os.environ['ENG_CORE_TRUST']=str(LOCAL/'host-trust.bin')
    os.environ['ENG_CORE_GOLDEN']=str(LOCAL/'host-golden.bin')
    os.environ['ASAN_OPTIONS']='detect_leaks=0:halt_on_error=1';os.environ['UBSAN_OPTIONS']='halt_on_error=1:print_stacktrace=1'
    rows=[]
    cases=[('slots',0),('tweaks',0),('t1',0),('startup',0),('startup-fail',0),('startup-write-fail',0),
           ('grain',0),('golden',0),('metadata',0),('short-s',0),('wide-wb',0),('identity',0),('rebind',0),('reentry',0),('no-wb',0),('entries',0),('entries-failure',0),('bad-pin',0),('old-sha',0),('bad-entry-crc',0),('stock-range',0),('cap24',0),('cap32',0),('cap32-over',0),('cap48',0)]
    cases += [('failw',n) for n in range(1,159)]
    cases += [('failx',n) for n in range(1,9)] + [('failv',n) for n in range(1,10)] + [('epoch',1),('patch',0),('preview',0),('release',0),('end',0)]
    for unit in range(3):
        for case,at in cases:
            label=f'host-{unit}-{case}-{at}'
            fixture=LOCAL/('host-max-data.bin' if case=='cap48' else 'host-stress.bin')
            out=run([binary,fixture,case,unit,at],label)
            rows.append(dict(unit=unit,case=case,at=at,result='pass',log=label+'.log'))
    run([binary,LOCAL/'host-stress.bin','parser',0,0],'host-parser');rows.append(dict(case='parser',result='pass'))
    legacy=load(HERE/'legacy_verify.py','task_legacy_verify').verify()
    result=dict(legacy_cases=legacy['cases'],sanitizers=['ASan','UBSan'],flags=flags,cases=rows,total=len(rows),
        source_hashes={str(p.relative_to(ROOT)):sha(p) for p in sources},host_only=True,camera_acceptance=False)
    (LOCAL/'tests.json').write_text(json.dumps(result,indent=2)+'\n')
    print(f"PASS: {len(rows)} processes, production C, ASan+UBSan; 3 units x 16 slots")
if __name__=='__main__':main()
