"""Complete the no-sample suite with the existing process-watch test isolated."""
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[1]
TMP=Path('/Volumes/Workspace/Scratch/tmp/projectricoh/review-studio-hdr')
MIRROR=TMP/'portable/studio'
NODE='tests/test_clone_coverage.py::test_worker_result_files_and_parent_watch'

if len(sys.argv)==1:
    frozen=json.loads((OUT/'frozen_inputs.json').read_text())
    for name,receipt in frozen['files'].items():
        if name.startswith('studio/') and not name.startswith('studio/.git/'):
            p=MIRROR/name[len('studio/'):]
            assert hashlib.sha256(p.read_bytes()).hexdigest()==receipt['sha256'],name
    parts=[]
    for part in ['remaining','worker']:
        r=subprocess.run([sys.executable,'-I','-B',str(Path(__file__).resolve()),part],check=False,timeout=2700)
        receipt=OUT/('portable_'+part+'_finish.json')
        if not receipt.exists():
            raise SystemExit('pytest did not finish: '+part+' exit '+str(r.returncode))
        finished=json.loads(receipt.read_text())
        assert r.returncode==finished['exit_status']
        parts.append(finished)
    summary={'parts':parts,'passed':sum(p['passed'] for p in parts),'failed':sum(p['failed'] for p in parts),
             'skipped':sum(p['skipped'] for p in parts),'reruns':sum(p['reruns'] for p in parts),'complete':True}
    (OUT/'portable_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary),flush=True)
    raise SystemExit(int(any(p['exit_status'] for p in parts)))

part=sys.argv[1]
assert part in ['remaining','worker']
os.chdir(MIRROR)
sys.path[:0]=[str(MIRROR/'src'),str(MIRROR/'tests')]
import pytest

class PortableConditions:
    def pytest_configure(self,config):
        import hdr_support as hs
        import gxr_studio
        assert Path(gxr_studio.__file__).resolve().is_relative_to(MIRROR)
        hs.ON_MACOS=False
        hs.HAS_IMAGEIO=False
        hs.needs_imageio=pytest.mark.skipif(True,reason='review: ImageIO unavailable condition')

    def pytest_sessionfinish(self,session,exitstatus):
        reporter=session.config.pluginmanager.get_plugin('terminalreporter')
        stats=reporter.stats
        result={'part':part,'exit_status':int(exitstatus),'collected':session.testscollected,
                'passed':len(stats.get('passed',[])),'failed':len(stats.get('failed',[])),
                'skipped':len(stats.get('skipped',[])),'deselected':len(stats.get('deselected',[])),
                'errors':len(stats.get('error',[])),'reruns':len(stats.get('rerun',[])),
                'failures':[r.nodeid for r in stats.get('failed',[])]}
        (OUT/('portable_'+part+'_finish.json')).write_text(json.dumps(result,indent=2)+'\n')

args=['-q','--durations=5','--force-reruns','0','--cov=gxr_studio','--cov-report=term']
if part=='remaining':
    args+=['--deselect='+NODE,'--cov-fail-under=0']
else:
    args+=[NODE,'--cov-append','--cov-fail-under=85']
raise SystemExit(pytest.main(args,plugins=[PortableConditions()]))
