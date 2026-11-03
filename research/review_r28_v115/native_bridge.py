"""Feed real C H01/H02 results into the byte-checked native constructor.

Unlike the inherited first-frame projection, the real native push resets part 2
and leaves count=1. External native calls remain explicit stubs.
"""
import importlib.util
import json
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
CAND=ROOT/'firmware/engine_v36_r28/candidate'

def load(path,name):
    s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m

EXTENSION=r'''
static void bridge_export(void)
{
    unsigned kind,row,i;uint32_t f[32],g[32],names;
    for(kind=0;kind<4;kind++)for(row=1;row<=8;row++){
        clean();ready(0);seed_last34(row);
        if(kind==1)native_writer_exposure();
        if(kind==2)native_writer_white_balance();
        if(kind==3)native_writer_image();
        RV_BYTE(RV_NATIVE_VIEWS)=32;RV_WORD(RV_NATIVE_VIEWS+4)=0x2022d610;
        RV_BYTE(0x205a27d4)=1;
        memset(f,0,sizeof(f));rv_hook_observe(&root,1,f);
        CHECK(root.state==RV_READY&&f[1]&&f[15]==row&&session()->rows==8);
        CHECK(RV_BYTE(0x2022f71c)==(kind==0?0:kind==1?4:kind==2?9:5));
        CHECK(RV_WORD(0x2022f720)==0x2022f56c&&RV_BYTE(0x2022f5ac)==8);
        CHECK(RV_BYTE(0x205a27d4)==1&&RV_BYTE(RV_NATIVE_VIEWS)==32);
        CHECK(!has_recipe()&&!rpc_calls&&!rpc_w&&!writes&&!previews);
        names=RV_WORD(0x2022f5a8);CHECK(names!=0x2022d610);
        for(i=0;i<8;i++)CHECK(RV_WORD(names+4*i));
        memset(g,0,sizeof(g));rv_hook_observe(&root,2,g);
        CHECK(g[1]&&g[7]==row);
        printf("BRIDGE {\"unit\":%u,\"kind\":%u,\"row\":%u,\"names\":%u,\"count\":8,\"h02_r8\":%u}\n",
            unit,kind==0?0:kind==1?4:kind==2?9:5,row,names,g[7]);
    }
}
'''

def main():
    h=load(HERE/'host_review.py','delta_bridge_host');h.OUT=HERE/'bridge';h.OUT.mkdir(exist_ok=True)
    source=(HERE/'host/host_v34c.c').read_text()
    source=source.replace('int main(int argc,char **argv)',EXTENSION+'\nint main(int argc,char **argv)')
    source=source.replace('if(!strcmp(argv[1],"review"))','if(!strcmp(argv[1],"bridge"))bridge_export();\n    else if(!strcmp(argv[1],"review"))')
    path=h.OUT/'bridge.c';path.write_text(source)
    flags=['-std=c11','-O1','-g','-Wall','-Wextra','-Werror','-Wno-unused-function','-fno-omit-frame-pointer',
        '-fsanitize=address,undefined','-fno-sanitize-recover=all','-DRV_HOST','-DENG_HOST',
        '-DPN_CORE_HEADER="../core/eng_core.h"','-DPN_GXTS_SHARED_PARAMETER',
        '-DACCEPTANCE_ENTRIES_HEADER="'+str(CAND/'local/product-r13/entries.h')+'"',
        '-I',CAND/'containers/product','-I',CAND,'-I',ROOT/'firmware/resident_v34c/resident']
    obj=h.OUT/'bridge.o';h.run(['/usr/bin/clang',*flags,'-c',path,'-o',obj],'compile-bridge')
    objects=sorted((HERE/'host').glob('[0-9][0-9]-*.o'))
    assert len(objects)==36
    binary=h.OUT/'bridge';h.run(['/usr/bin/clang',*flags,*objects,obj,'-o',binary],'link-bridge')
    rows=[];final=CAND/'local/full-r13'
    for unit in range(3):
        out=h.run([binary,'bridge',unit,final/'GXRCE.DAT',final/'trust.bin',final/'effective-rows.bin',
            ROOT/'firmware/resident_v34c/acceptance/local/full-r11/GXRCE.DAT','0'],f'C-bridge-{unit}')
        rows.extend(json.loads(line[7:]) for line in out.splitlines() if line.startswith('BRIDGE '))
    assert len(rows)==96 and sum(x['unit']==1 for x in rows)==32
    n=load(HERE/'native_flow.py','bridge_native_cpu');program=n.Program();results=[]
    for row in rows:
        for category in (0,1):
            cpu=n.Cpu(program)
            cpu.seed(0x205a27d8,0x205a279c);cpu.seed(0x205a27d4,1,1)
            cpu.seed(0x205a279c,32,1);cpu.seed(0x205a27a0,0x2022d610)
            cpu.seed(0x205a280e,2,1);cpu.seed(0x205a280f,2,1)
            cpu.seed(0x2022f71c,row['kind'],1)
            for i,v in enumerate((1,2,3,4,5)):cpu.seed(0x205d9bcc+i,v,1)
            no_op=lambda c:c.r.__setitem__(0,0)
            cpu.stubs={addr:no_op for addr in (0x20331d18,0x20331d14,0x201d82b4,
                0x201c3fd4,0x201d82fc,0x201c092c,0x20270d78)}
            cpu.stubs[0x2026c314]=lambda c:c.r.__setitem__(0,category)
            def bridge(c):
                assert c.read(0x2022f71c,1)==row['kind'] and c.read(0x2022f720)==0x2022f56c
                c.seed(0x2022f5a8,row['names']);c.seed(0x2022f5ac,row['count'],1)
                c.seed(0x2022f725,row['row'],1);c.seed(0x2022f726,row['row'],1)
                c.r[8]=row['h02_r8'];return 0x20287118
            cpu.handlers[0x2028709c]=bridge
            cpu.run('constructor')
            assert cpu.read(0x2022f71c,1)==5 and cpu.read(0x2022f720)==0x2022f56c
            assert cpu.read(0x2022f5a8)==row['names'] and cpu.read(0x2022f5ac,1)==8
            assert cpu.read(0x2022f725,1)==row['row'] and cpu.read(0x2022f726,1)==row['row']
            assert cpu.read(0x205a27d4,1)==1 and cpu.read(0x205a279c,1)==33 and cpu.read(0x205a27a0)==0x2022f71c
            results.append(dict(**row,category=category,final_type=5,view_count=1,top_tag=33,top_state='0x2022f71c'))
    (h.OUT/'results.json').write_text(json.dumps(dict(C_H01_H02=rows,native_continuations=results,
        limits=['Actual C hook results cross a process boundary into a bounded native CPU model.',
                'Native graphics, scheduler, category probes and interrupt boundaries remain stubs.']),indent=2)+'\n')
    print('PASS C H01/H02',len(rows),'cases; byte-checked native continuations',len(results),'including all qlaunch rows/types')

if __name__=='__main__':main()
