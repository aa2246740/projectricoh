"""Bounded foreground driver; preserve finished fits and frozen scene selection."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bootstrap as b
import argparse
import subprocess


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--dry-run',action='store_true');args=parser.parse_args()
    tasks=[('bootstrap.py',[],b.LOCAL/'protected_before.json'),
           ('prepare.py',[],b.LOCAL/'datasets.json')]
    for ridge in (0.5,2.0,8.0):
        for ident in ('hdf_positive','gr4b_positive'):
            tasks.append(('fit.py',['--ridge',str(ridge),'--leave',ident],
                          b.LOCAL/'fits'/f'ridge_{ridge}_leave_{ident}.json'))
    tasks += [('fit.py',['--select'],b.LOCAL/'selection.json'),
              ('fit.py',['--final'],b.LOCAL/'gr4_positive_01.json'),
              ('evaluate.py',[],b.HERE/'scores.json')]
    scenes=[('cc24','captures/a12-50/2026-10-21/chart-closedloop/R8051207.JPG'),
            ('ring','captures/a12-50/2026-10-21/screen-closedloop/R8051198.JPG'),
            ('cc24_earlier','captures/a12-50/2026-10-19/stage2d-colorchecker/R8051151.JPG'),
            ('red_stilllife','captures/a12-50/2026-10-16/S1b-sd-import/DCIM/100RICOH/R8051131.DNG')]
    for ident,source in scenes:
        tasks.append(('preview.py',['--scene',ident,'--source',source],b.LOCAL/'previews'/(ident+'_manifest.json')))
    tasks += [('report.py',[],b.HERE/'REPORT.md'),('verify.py',['--seal'],b.HERE/'SHA256SUMS')]
    for script,argv,done in tasks:
        if done.exists():
            print('RETAIN',script,' '.join(argv),flush=True)
            continue
        command=['python3','-I','-B',str(b.HERE/script),*argv]
        print('MISSING',script,' '.join(argv),flush=True)
        if not args.dry_run:
            subprocess.run(command,cwd=b.ROOT,check=True,timeout=55)
    if not args.dry_run:
        subprocess.run(['python3','-I','-B',str(b.HERE/'verify.py')],cwd=b.ROOT,check=True,timeout=55)


if __name__=='__main__':main()
