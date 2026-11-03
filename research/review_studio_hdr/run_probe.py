"""Synchronous, time-bounded runner for independent review probes."""
import importlib.util
import json
import os
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

OUT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('review_env', OUT / 'run_check.py')
review_env = importlib.util.module_from_spec(spec)
spec.loader.exec_module(review_env)

def main():
    label = sys.argv[1]
    assert label in ['alignment','format','format_detail','edits','paths','paths_detail','platform','portable','portable_detail','alignment_detail','export_imageio','export_paths']
    assert not (OUT / (label + '_run.json')).exists()
    profile = OUT / ('review_loopback.sb' if label in ['portable','portable_detail'] else 'review.sb')
    argv = ['/usr/bin/sandbox-exec','-f',str(profile),'/usr/bin/nice','-n','10',
            str(review_env.ROOT/'studio/.venv/bin/python'),'-I','-B',str(OUT/('probe_'+label+'.py'))]
    env = review_env.environment()
    env['PYTHONUNBUFFERED'] = '1'
    env['COVERAGE_FILE'] = str(review_env.TMP / ('coverage-'+label))
    env['PYTEST_ADDOPTS'] = '--basetemp='+str(review_env.TMP/('pytest-'+label))+' --force-reruns 0'
    record = {'utc_start':datetime.now(timezone.utc).isoformat(),'argv':argv,'timeout_seconds':5400}
    (OUT/(label+'_started.json')).write_text(json.dumps(record,indent=2)+'\n')
    started = time.monotonic()
    with (OUT/(label+'.log')).open('xb') as log:
        process = subprocess.Popen(argv,cwd=review_env.ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        try:
            code = process.wait(timeout=5400)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid,signal.SIGTERM)
            process.wait(timeout=30)
            code = 124
    record.update(exit_code=code,seconds=round(time.monotonic()-started,3),utc_end=datetime.now(timezone.utc).isoformat())
    (OUT/(label+'_run.json')).write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps(record))
    print('\n'.join((OUT/(label+'.log')).read_text(errors='replace').splitlines()[-6:]))
    return code

if __name__ == '__main__':
    raise SystemExit(main())
