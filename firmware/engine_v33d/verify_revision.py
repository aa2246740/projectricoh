"""R6 counterexamples become positive behavior checks; no protected writes."""
import argparse
import json
from pathlib import Path
import re
import sys

sys.path.insert(0,str(Path(__file__).resolve().parent))
import common as c
import verify as inherited


def compile_drivers():
    support=(c.HERE/'host_v33.c').read_text()
    assert support.count('int main(int argc,char **argv)')==1
    c.write(c.LOCAL/'review_support.c',support.replace('int main(int argc,char **argv)','int inherited_v33_main(int argc,char **argv)').encode())
    calls=[json.loads(line) for line in (c.LOCAL/'commands.jsonl').read_text().splitlines()]
    template=next(row['argv'] for row in reversed(calls) if re.fullmatch(r'host-compile-\d+',row['label']) and str(c.HERE/'host.c') in row['argv'])
    link=next(row['argv'] for row in reversed(calls) if row['label']=='host-link')
    original=template[template.index('-o')+1]
    proof=[]
    for name in ('host_r6_cases','host_revision'):
        obj=c.LOCAL/'host'/(name+'.o');source=c.HERE/(name+'.c')
        command=[str(source) if arg==str(c.HERE/'host.c') else str(obj) if arg==original else arg for arg in template]
        c.run([command[0],'-I',c.HERE,*command[1:]],'compile-'+name)
        command=[str(obj) if arg==original else arg for arg in link];command[command.index('-o')+1]=str(c.LOCAL/'host'/name)
        c.run(command,'link-'+name)
        proof.append(dict(name=name,source_sha256=c.sha(source),binary_sha256=c.sha(c.LOCAL/'host'/name),support_sha256=c.sha(c.LOCAL/'review_support.c')))
    c.save(c.LOCAL/'revision-driver-proof.json',proof)


def reviewer():
    for policy in (0,1):
        for unit in (0,2):
            for case in ('parent-empty','parent-remember03','poison-write-panel','poison-write-same','poison-rename-panel','poison-close-same','survivor-A','survivor-B','survivor-AB','write-frequency'):
                inherited.execute('host_r6_cases',case,unit,105,[policy])
        for case in ('unit-swap28','unit-swapM0'):
            inherited.execute('host_r6_cases',case,0,105,[policy])
    assert len(inherited.RESULTS)==44


def boundary():
    for policy in (0,1):
        for unit in (0,2):
            for action in (0,1):
                for mode in (*range(11),11,255):
                    inherited.execute('host_revision','boundary',unit,105,[policy,mode,action,0])
                for remembered in (1,3,5,8):
                    inherited.execute('host_revision','boundary',unit,105,[policy,1,action,remembered])
    assert len(inherited.RESULTS)==136


def policy():
    for rename in (0,1):
        for unit in (0,2):
            inherited.execute('host_revision','write-policy',unit,105,[rename])
            for stage in (5,15,6,7):
                for key in (0,1,2):
                    inherited.execute('host_revision','forced-during',unit,105,[rename,stage,key])
    assert len(inherited.RESULTS)==52


def upgrade():
    for generation in (105,106,107,108):
        for rename in (0,1):
            for unit in range(3):
                inherited.execute('host_revision','upgrade-memory',unit,generation,[rename])
                inherited.execute('host_revision','older-card-close',unit,generation,[rename])
                if generation==108:
                    for name in ('upgrade-empty','upgrade-saved'):
                        inherited.execute('host_v33',name,unit,generation,[rename])
    assert len(inherited.RESULTS)==60


def main():
    p=argparse.ArgumentParser();p.add_argument('phase',choices=('compile','reviewer','boundary','policy','upgrade'));args=p.parse_args()
    c.guard();c.freeze_check()
    if args.phase=='compile':compile_drivers()
    else:
        globals()[args.phase]()
        for row in inherited.RESULTS:
            log=(c.HERE/row['log']).read_text()
            if 'KNOWN_LIMITATION_CHECK' in log or 'native_initialization_overwrites' in log:
                row['status']='KNOWN_LIMITATION_CHECK'
            if 'resident_retires_on_unit_change' in log:
                row['status']='INHERITED_UNIT_SWAP_CHECK'
        c.save(c.LOCAL/('revision-'+args.phase+'-results.json'),dict(status='PASS',host_runs=len(inherited.RESULTS),cases=inherited.RESULTS))
    c.freeze_check();print(json.dumps(dict(status='PASS',phase=args.phase,host_runs=len(inherited.RESULTS))))


if __name__=='__main__':main()
