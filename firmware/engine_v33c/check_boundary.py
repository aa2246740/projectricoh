"""Recompile unchanged full-r6 C, replay review cases and first-build assertions.

Nonzero first-build results are retained as failures, never accepted as a fix.
No candidate container or resident is built by this program.
"""
from pathlib import Path
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as c
import host_compile


def main():
    c.guard();c.freeze_check()
    upstream=c.ROOT/'firmware/engine_v33b'
    product=c.LOCAL/'product';product.mkdir(exist_ok=True)
    c.write(product/'entries.h',(upstream/'local/product/entries.h').read_bytes())
    sys.path.insert(0,str(c.PRODUCT))
    build=c.load(c.PRODUCT/'build.py','boundary_product_build')
    host_compile.compile_all(build)
    support=(c.HERE/'host_v33.c').read_text()
    assert support.count('int main(int argc,char **argv)')==1
    c.write(c.LOCAL/'review_support.c',support.replace('int main(int argc,char **argv)',
              'int inherited_v33_main(int argc,char **argv)').encode())
    calls=[json.loads(line) for line in (c.LOCAL/'commands.jsonl').read_text().splitlines()]
    compile_cmd=next(r['argv'] for r in calls if r['label'].startswith('host-compile-') and str(c.HERE/'host.c') in r['argv'])
    fixture_obj=compile_cmd[compile_cmd.index('-o')+1]
    link_cmd=next(r['argv'] for r in calls if r['label']=='host-link')
    sources=[('review',c.ROOT/'research/review_full_r6/host_review.c'),('boundary',c.HERE/'host_boundary.c')]
    for name,source in sources:
        obj=c.LOCAL/'host'/(name+'.o')
        args=[str(source) if a==str(c.HERE/'host.c') else str(obj) if a==fixture_obj else a for a in compile_cmd]
        c.run([*args[:1],'-I',c.HERE,*args[1:]],'compile-'+name)
        args=[str(obj) if a==fixture_obj else a for a in link_cmd]
        args[args.index('-o')+1]=str(c.LOCAL/'host'/name)
        c.run(args,'link-'+name)
    old=c.ROOT/'firmware/engine_fix_r2/local/product/candidates/full-r3'
    new=upstream/'local/full-r6'
    def execute(binary,name,unit,policy,extra=()):
        label=f'{binary}-{name}-{unit}-{policy}'+''.join('-'+str(v) for v in extra)
        r=c.run([c.LOCAL/'host'/binary,name,unit,old/'GXRCE.DAT',new/'GXRCE.DAT',new/'trust.bin',
                 old/'effective-rows.bin',new/'effective-rows.bin',policy,*extra],label,check=False)
        return dict(name=name,unit=unit,policy=policy,extra=list(extra),returncode=r.returncode,
                    log='local/logs/'+label+'.log',output=r.stdout+r.stderr)
    cases=[]
    for unit in (0,2):
        for policy in (0,1):
            for name in ('parent-empty','parent-remember03','poison-write-panel','poison-write-same',
                         'poison-rename-panel','poison-close-same','write-frequency'):
                row=execute('review',name,unit,policy);assert row['returncode']==0
                cases.append(row)
    failures=[]
    for unit in (0,2):
        for remembered in (0,1,3,5,8):
            row=execute('boundary','first-build',unit,1,[remembered]);cases.append(row)
            if row['returncode']:
                assert row['returncode']==1 and 'FAIL_REQUIRED_CURSOR' in row['output']
                failures.append(row)
    summary=dict(status='STOP_R6_01_NO_EXISTING_LATE_ENGINE_CALLBACK',runs=len(cases),
                 reproduced_review_counterexamples=24,write_frequency_observations=4,
                 first_build_required_assertions=10,first_build_failures=len(failures),
                 product_assertions_pass=False,candidate_built=False,camera_acceptance=False,cases=cases)
    assert len(failures)>0
    c.save(c.LOCAL/'boundary-results.json',summary)
    c.freeze_check()
    print(json.dumps({k:v for k,v in summary.items() if k!='cases'}))
    raise SystemExit(1)


if __name__=='__main__':main()
