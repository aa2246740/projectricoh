"""Run the unchanged auditor with an explicit record inventory and provenance."""
from pathlib import Path
import argparse
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from run import run
OUT=Path(__file__).resolve().parent;ROOT=OUT.parents[1]
p=argparse.ArgumentParser();p.add_argument('--source',choices=('supplied','rerun'),required=True)
p.add_argument('--users',action='store_true');p.add_argument('--tag',default='');a=p.parse_args()
source=ROOT/'research/g124_ui_v2' if a.source=='supplied' else OUT
if a.users:
    records=[source/'local'/('users-'+u+'.json') for u in ('50mm','28mm','mount')]
    if a.source=='rerun':records += [source/'local'/('other-users-'+u+'.json') for u in ('50mm','28mm','mount')]
    dat=OUT/'local/user-fixture-ebf07faa3c5b/GXRCE.DAT'
else:
    records=[source/'local'/n for n in ('ui-cases','cases','safety','lock-cases','nested','cutpoints-irq-enabled','view-reentry','lock-exits')]
    records += [source/'local'/('official-half-'+u+'-with-hooks.json') for u in ('50mm','28mm','mount')]
    records += [source/'local'/('labels-'+u+'.json') for u in ('50mm','28mm','mount')]
    records += ([source/'local/remaining-window.json'] if a.source=='supplied' else
                [OUT/'local/reentry-all-keys-final',*sorted((OUT/'local/window-consequences').glob('124-*.json'))])
    dat=ROOT/'firmware/package_v36_g124/SD_ROOT/GXRCE.DAT'
records=[path for path in records if path.exists()]
label='rpc-'+a.source+('-users' if a.users else '-default')+'-complete'
argv=['/usr/bin/python3','-I','-B',str(ROOT/'research/g122_keep_list/audit_records.py'),'--dat',str(dat),
      '--records',*map(str,records),'--output',str(OUT/'evidence'/(label+'.json')),'--base-dir',str(ROOT)]
raise SystemExit(run(label+a.tag,argv))
