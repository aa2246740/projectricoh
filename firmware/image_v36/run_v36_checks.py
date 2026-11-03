"""Run copied reviewer scripts; preserve each command, exit status and output."""
import argparse,json,os,subprocess,time
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];REVIEW=HERE/'local/review'
GROUPS={
 'matrix':[('matrix','adversarial.py')],
 'faults':[('h08-retire','h08_retire.py'),('h08-first','h08_first_fault.py'),('scroll-both','scroll_both.py'),('p2','p2_gates.py')],
 'guards':[('extra','extra_scenarios.py'),('h06-nested','reachability.py','h06'),('ownership','ownership.py'),('h06-fault','h06_fault.py')],
 'supplement':[('menu-native','menu_native.py'),('deep-bytes','deep_bytes.py')],
}
def main():
 p=argparse.ArgumentParser();p.add_argument('group',choices=GROUPS);args=p.parse_args();records=[]
 for label,script,*rest in GROUPS[args.group]:
  argv=['/usr/bin/python3','-I','-B',str(REVIEW/script),*rest];start=time.monotonic()
  with (REVIEW/(label+'.stdout.log')).open('w') as stdout,(REVIEW/(label+'.stderr.log')).open('w') as stderr:
   result=subprocess.run(argv,cwd=ROOT,stdout=stdout,stderr=stderr,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'))
  records.append(dict(label=label,argv=argv,returncode=result.returncode,seconds=round(time.monotonic()-start,3)))
  (REVIEW/('executions-'+args.group+'.json')).write_text(json.dumps(records,indent=2)+'\n')
  print(label,'exit',result.returncode,flush=True)
  if result.returncode:return result.returncode
 return 0
if __name__=='__main__':raise SystemExit(main())
