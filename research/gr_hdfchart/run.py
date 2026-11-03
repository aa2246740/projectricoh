"""Bounded sequential reproduction. No camera, network, fitting or background jobs."""
import sys
sys.dont_write_bytecode=True
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import support as s
import argparse
import subprocess


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--data-root',type=Path,required=True)
    ap.add_argument('--stage',choices=('all','extract','score','correct','supplement','report'),default='all')
    a=ap.parse_args();s.guard();s.snapshot()
    data=a.data_root.resolve();assert data.is_relative_to(s.ROOT/'captures')
    def call(name,*args):
        subprocess.run([sys.executable,'-I','-B',str(s.HERE/name),*map(str,args)],cwd=s.ROOT,check=True)
    def source(ident):
        paths=list((data/'dng').glob('*_'+ident+'.DNG'))
        assert len(paths)==1,(ident,paths)
        return paths[0]
    if a.stage in ('all','extract'):
        for ident in ('R0003037','R0003039'):
            call('extract_chart.py','--dng',source(ident),'--jpeg',data/'embedded'/(ident+'_embedded.jpg'),'--id',ident)
    if a.stage in ('all','score'):call('score_chart.py')
    if a.stage in ('all','correct'):call('correct_targets.py')
    if a.stage in ('all','supplement'):
        call('supplement.py','--white-dng',source('R0003036'),'--white-dng',source('R0003038'))
    if a.stage in ('all','report'):call('report.py')


if __name__=='__main__':
    main()
