"""Sequential independent replay commands for one unit; no polling or devices."""
from pathlib import Path
import argparse
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from run import run
OUT=Path(__file__).resolve().parent
GROUPS={
 'cold':['cold_reentry.py'],
 'suite':['run_cases.py','suite'],
 'safety':['safety_cases.py'],
 'locked':['locked_cases.py'],
 'nested':['lock_nested.py','--cuts','record_failure_return','after_update_restore','before_redraw','row_draw'],
 'cutpoints':['lock_cutpoints.py','--irq-enabled'],
 'exits':['lock_exits.py'],
 'transitions':['ui_acceptance.py','transitions'],
 'values':['ui_acceptance.py','values'],
 'view-reentry':['view_reentry.py'],
 'reentry-six':['reentry_all_keys.py'],
 'users':['user_acceptance.py'],
 'other-users':['other_users.py'],
 'project':['project_boundary.py'],
 'labels':['label_acceptance.py'],
 'half':['official_half.py','--hook-trace'],
}
def main():
    p=argparse.ArgumentParser();p.add_argument('--unit',choices=('50mm','28mm','mount'),required=True)
    p.add_argument('--groups',nargs='+',choices=GROUPS,default=list(GROUPS))
    p.add_argument('--tag',default='batch');args=p.parse_args();codes=[]
    for group in args.groups:
        name,*rest=GROUPS[group]
        argv=['/usr/bin/python3','-I','-B',str(OUT/name),*rest]
        argv+=([args.unit] if group=='locked' else ['--unit',args.unit])
        codes.append(run(args.tag+'-'+group+'-'+args.unit,argv,timeout=1500))
        sys.stdout.flush()
    raise SystemExit(int(any(codes)))
if __name__=='__main__':main()
