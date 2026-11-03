"""Run the unchanged supplied auditor on final and user-variant complete streams."""
from pathlib import Path
import json
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import *

def main():
    roots=[OUT/'local'/name for name in ('ui-cases','cases','safety','lock-cases','nested','cutpoints-irq-enabled','view-reentry','lock-exits')]
    roots += [OUT/'local'/f'official-half-{unit}-with-hooks.json' for unit in ('50mm','28mm','mount')]
    roots += [OUT/'local'/f'labels-{unit}.json' for unit in ('50mm','28mm','mount')]
    roots += [OUT/'local/remaining-window.json']
    assert all(path.exists() for path in roots),[str(path) for path in roots if not path.exists()]
    auditor=ROOT/'research/g122_keep_list/audit_records.py'
    result=run(['/usr/bin/python3','-I','-B',auditor,'--dat',DAT,'--records',*roots,
                '--output',OUT/'evidence/rpc-audit.json','--base-dir',ROOT], 'rpc-audit-final')
    print(result.stdout.strip())
    fixture=ROOT/json.loads((OUT/'evidence/user-tool.json').read_text())['fixture']
    result=run(['/usr/bin/python3','-I','-B',auditor,'--dat',fixture,'--records',
                *[OUT/'local'/f'users-{unit}.json' for unit in ('50mm','28mm','mount')],
                '--output',OUT/'evidence/rpc-users.json','--base-dir',ROOT], 'rpc-audit-users')
    print(result.stdout.strip())
    for name in ('rpc-audit','rpc-users'):
        value=json.loads((OUT/'evidence'/(name+'.json')).read_text())
        assert value['status']=='PASS' and not value['excluded_other_dat']
        assert all(value['coverage'][unit]['raw_streams_present'] for unit in ('50mm','28mm','mount'))

if __name__=='__main__':main()
