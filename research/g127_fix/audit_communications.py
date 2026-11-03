#!/usr/bin/python3
"""Feed complete retained streams to the original communication reviewer."""
from pathlib import Path
import hashlib,json,subprocess
ROOT=Path(__file__).resolve().parents[2]
WORK=ROOT/'research/g127_fix'
RUNS=WORK/'local/release127'
DEFAULT=ROOT/'firmware/package_v36_g127/local/SD_ROOT/GXRCE.DAT'
PIN=hashlib.sha256(DEFAULT.read_bytes()).hexdigest()
registry={PIN:DEFAULT}
for p in RUNS.rglob('*'):
 if p.is_file() and p.suffix.upper()=='.DAT':registry[hashlib.sha256(p.read_bytes()).hexdigest()]=p

def streams(value):
 if isinstance(value,dict):
  for v in value.values():yield from streams(v)
 elif isinstance(value,list) and value and all(isinstance(x,dict) and {'cmd','value','page','result'}<=x.keys() for x in value):yield value

groups={};skipped=[]
for p in RUNS.rglob('*.json'):
 try:x=json.loads(p.read_text())
 except (ValueError,OSError):continue
 if not isinstance(x,dict) or not list(streams(x)):continue
 pin=x.get('dat_sha256') or x.get('artifact',{}).get('dat_sha256')
 if pin not in registry:
  skipped.append({'path':str(p.relative_to(ROOT)),'reason':'DAT identity unavailable'});continue
 groups.setdefault(pin,[]).append(p)
results=[]
for pin,paths in groups.items():
 output=WORK/'evidence'/('rpc-'+pin[:12]+'.json')
 command=['/usr/bin/python3','-I','-B',str(ROOT/'research/g122_keep_list/audit_records.py'),'--dat',str(registry[pin]),'--records']+[str(p) for p in paths]+['--output',str(output),'--base-dir',str(ROOT)]
 with (WORK/'local'/('rpc-'+pin[:12]+'.log')).open('w') as log:
  code=subprocess.run(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT).returncode
 results.append({'dat_sha256':pin,'dat':str(registry[pin].relative_to(ROOT)),'records':len(paths),'returncode':code,'output':str(output.relative_to(ROOT))})
summary={'default_dat_sha256':PIN,'groups':results,'skipped':skipped,'sentinel_option_used':False}
(WORK/'evidence/rpc-summary.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary))
