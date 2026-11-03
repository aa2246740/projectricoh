"""Run added recovery and withdrawal checks sequentially per unit."""
from pathlib import Path
import argparse
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from run import run

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--unit',choices=('50mm','28mm','mount'),required=True)
    p.add_argument('--groups',nargs='+',default=['cold-exits','settings','withdrawal','cold-matrix','preview-reopen'])
    p.add_argument('--tag',default='r1')
    args=p.parse_args()
    out=Path(__file__).resolve().parent
    groups=[('cold-exits','cold_exit.py',[]),('settings','settings_cases.py',[]),
            ('withdrawal','transition_discipline.py',['--irq-enabled']),
            ('cold-matrix','cold_exit_matrix.py',[]),('preview-reopen','preview_reopen.py',[])]
    codes=[]
    choices={label:(script,extra) for label,script,extra in groups}
    for label in args.groups:
        script,extra=choices[label]
        if label=='cold-matrix' and args.tag!='r1':extra=[*extra,'--tag=-'+args.tag]
        codes.append(run(args.tag+'-'+label+'-'+args.unit,
            ['/usr/bin/python3','-I','-B',str(out/script),'--unit',args.unit,*extra],timeout=1200))
    raise SystemExit(int(any(codes)))

if __name__=='__main__':main()
