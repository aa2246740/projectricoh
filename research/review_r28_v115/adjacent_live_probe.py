"""Negative probe: change only B5's live neighbour between two applies.

This does not establish that a native camera writer can make the same change.
It exposes the cache assumption separately from a hardware-reachable defect.
"""
import importlib.util
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
CAND=ROOT/'firmware/engine_v36_r28/candidate'
EXTENSION=r'''
static void changing_neighbor_probe(void)
{
    uint32_t map=be32(new_raw+be32(new_raw+156)+64*unit+12);
    uint32_t neighbor=be32(new_raw+map+24)+1;
    unsigned first,after;
    clean();ready(0);menu();RV_BYTE(neighbor)=0x5a;
    apply_ok(1);CHECK(RV_BYTE(neighbor)==0x5a);
    first=RV_BYTE(neighbor);RV_BYTE(neighbor)=0xa5;
    menu();apply_ok(2);after=RV_BYTE(neighbor);
    CHECK(root.state==RV_READY&&after==first);
    printf("PROBE {\"unit\":%u,\"neighbor_address\":%u,\"first_live\":90,\"later_live\":165,\"after_apply\":%u,\"hardware_writer_proven\":false}\n",
        unit,neighbor,after);
}
'''

def main():
    s=importlib.util.spec_from_file_location('neighbor_compile',HERE/'host_review.py')
    h=importlib.util.module_from_spec(s);s.loader.exec_module(h)
    h.OUT=HERE/'changing_neighbor';h.OUT.mkdir(exist_ok=True)
    source=(HERE/'host/host_v34c.c').read_text()
    source=source.replace('int main(int argc,char **argv)',EXTENSION+'\nint main(int argc,char **argv)')
    source=source.replace('if(!strcmp(argv[1],"review"))','if(!strcmp(argv[1],"changing-neighbor"))changing_neighbor_probe();\n    else if(!strcmp(argv[1],"review"))')
    path=h.OUT/'probe.c';path.write_text(source)
    flags=['-std=c11','-O1','-g','-Wall','-Wextra','-Werror','-Wno-unused-function','-fno-omit-frame-pointer',
        '-fsanitize=address,undefined','-fno-sanitize-recover=all','-DRV_HOST','-DENG_HOST',
        '-DPN_CORE_HEADER="../core/eng_core.h"','-DPN_GXTS_SHARED_PARAMETER',
        '-DACCEPTANCE_ENTRIES_HEADER="'+str(CAND/'local/product-r13/entries.h')+'"',
        '-I',CAND/'containers/product','-I',CAND,'-I',ROOT/'firmware/resident_v34c/resident']
    obj=h.OUT/'probe.o';h.run(['/usr/bin/clang',*flags,'-c',path,'-o',obj],'compile-probe')
    binary=h.OUT/'probe';h.run(['/usr/bin/clang',*flags,*sorted((HERE/'host').glob('[0-9][0-9]-*.o')),obj,'-o',binary],'link-probe')
    result=[];final=CAND/'local/full-r13'
    for unit in range(3):
        out=h.run([binary,'changing-neighbor',unit,final/'GXRCE.DAT',final/'trust.bin',final/'effective-rows.bin',
            ROOT/'firmware/resident_v34c/acceptance/local/full-r11/GXRCE.DAT','0'],f'probe-{unit}')
        result.extend(json.loads(line[6:]) for line in out.splitlines() if line.startswith('PROBE '))
    assert len(result)==3
    (h.OUT/'results.json').write_text(json.dumps(dict(classification='labelled negative; native writer reachability unknown',
        observations=result),indent=2)+'\n')
    print('REPRODUCED B5 neighbour cache assumption on three units; native writer reachability unproven')

if __name__=='__main__':main()
