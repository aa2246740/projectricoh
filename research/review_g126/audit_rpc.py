"""Run the unchanged gen 122 communication auditor on final replay records."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from support import *
from common import run

def main():
    auditor=ROOT/'research/g122_keep_list/audit_records.py'
    folders=('ui-cases','cases','safety','lock-cases','nested','cutpoints-irq-enabled',
             'view-reentry','lock-exits','reentry-all-keys','cold-reentry','settings-cases',
             'cold-exit','row-transitions-irq','window-consequences',
             'cold-exit-matrix-r2','ownership-settings','preview-reopen')
    records=[OUT/'local'/name for name in folders]
    records += [OUT/'local'/('official-half-'+unit+'-with-hooks.json') for unit in ('50mm','28mm','mount')]
    records += [OUT/'local'/('labels-'+unit+'.json') for unit in ('50mm','28mm','mount')]
    assert all(path.exists() for path in records)
    save('evidence/rpc-inputs.json',dict(default_records=[str(path.relative_to(ROOT)) for path in records],
         excluded_non_records='Build outputs, decoder caches, and deliberate malformed JSON CLI fixtures are not RPC records.',
         auditor=str(auditor.relative_to(ROOT)),auditor_sha256=file_sha(auditor)))
    run(['/usr/bin/python3','-I','-B',auditor,'--dat',DAT,'--records',*records,
         '--output',OUT/'evidence/rpc-default-complete.json','--base-dir',ROOT], 'rpc-default-complete')
    tool=json.loads((OUT/'evidence/user-tool.json').read_text())
    records=[OUT/'local'/(name+'-'+unit+'.json') for unit in ('50mm','28mm','mount') for name in ('users','other-users')]
    run(['/usr/bin/python3','-I','-B',auditor,'--dat',ROOT/tool['fixture'],'--records',*records,
         '--output',OUT/'evidence/rpc-users-complete.json','--base-dir',ROOT], 'rpc-users-complete')

if __name__=='__main__':
    main()
