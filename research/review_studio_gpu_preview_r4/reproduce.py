"""Fresh reproduction from the frozen sources, with automatic fixture cleanup."""
import argparse,datetime,hashlib,json,os,plistlib,re,shutil,signal,subprocess,sys,tempfile,time,traceback
from pathlib import Path
BUNDLE=Path(__file__).resolve().parent
WORKTREE=Path('/Volumes/Workspace/Scratch/worktrees/gxr-studio/gpu-preview')
FENCE=Path('/Volumes/Workspace/Scratch/tmp/projectricoh/review-gpu-r4')
HEAD='fb6bacc51a35ee56736f9af4de5aa624cfd4ac14'
CASES={'dat-root':'dat_root_variants.py','card-extra':'additional_card_cases.py','r3-extra':'extra_boundaries.py','r3-loop':'windows_loop_guard.py','r3-contracts':'windows_contracts.py',**{name:'replay_r2.py' for name in ['media_root_race','path_delete_race','card_reader_retarget','lut_reimport_probe','http_boundary_extra']}}
def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--case',choices=CASES,default='dat-root')
 parser.add_argument('--run-name',default='run-'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S'))
 args=parser.parse_args();assert re.fullmatch('[a-zA-Z0-9_-]+',args.run_name)
 os.setpriority(os.PRIO_PROCESS,0,max(10,os.getpriority(os.PRIO_PROCESS,0)))
 disk=plistlib.loads(subprocess.check_output(['/usr/sbin/diskutil','info','-plist','/Volumes/Workspace']))
 assert disk['VolumeUUID']=='14BE04EB-AF49-497E-B36A-B078B2F7C5E8' and disk['FilesystemType']=='apfs' and disk['WritableVolume']
 env={k:v for k,v in os.environ.items() if k not in ['GIT_DIR','GIT_WORK_TREE']};env['GIT_OPTIONAL_LOCKS']='0'
 actual=subprocess.check_output(['git','-C',str(WORKTREE),'rev-parse','HEAD'],env=env,text=True).strip();assert actual==HEAD,actual
 manifest=json.loads((BUNDLE/'source-before.json').read_text())
 for name,expected in manifest.items():assert hashlib.sha256((WORKTREE/name).read_bytes()).hexdigest()==expected,name
 run=FENCE/args.run_name;output=BUNDLE/'reproductions'/args.run_name
 assert not run.exists() and not output.exists(),'Use a fresh run name'
 run.mkdir(parents=True);output.mkdir(parents=True)
 source=run/'source';source.mkdir()
 for name in manifest:
  target=source/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(WORKTREE/name,target)
 for name in ['home','tmp','cache','fixtures']:(run/name).mkdir()
 for key in list(os.environ):
  if key.startswith(('GXR_','SENTRY_')):os.environ.pop(key)
 os.environ.update(HOME=str(run/'home'),TMPDIR=str(run/'tmp'),TMP=str(run/'tmp'),TEMP=str(run/'tmp'),XDG_CACHE_HOME=str(run/'cache'),PYTHONDONTWRITEBYTECODE='1',REVIEW_TMP=str(run/'fixtures'),REVIEW_SOURCE=str(source),REVIEW_OUT=str(output),OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',VECLIB_MAXIMUM_THREADS='1',NUMEXPR_NUM_THREADS='1')
 tempfile.tempdir=str(run/'tmp');sys.dont_write_bytecode=True
 os.chdir(source);sys.path.insert(0,str(source/'src'))
 script=BUNDLE/CASES[args.case];sys.argv=[str(script)]+([args.case] if script.name=='replay_r2.py' else [])
 started=time.monotonic();error=None
 signal.alarm(300)
 try:
  from contextlib import redirect_stdout,redirect_stderr
  with (output/'stdout.log').open('w') as stdout,(output/'stderr.log').open('w') as stderr,redirect_stdout(stdout),redirect_stderr(stderr):
   try:exec(compile(script.read_text(),str(script),'exec'),{'__file__':str(script),'__name__':'__main__'})
   except BaseException as exc:error=type(exc).__name__+':'+str(exc);traceback.print_exc()
 finally:
  signal.alarm(0)
  from gxr_studio import audit
  for root in audit.protected_roots():
   if Path(root).is_relative_to(run):audit.unprotect(root)
  os.chdir(BUNDLE);shutil.rmtree(run)
 changed=[name for name,h in manifest.items() if hashlib.sha256((WORKTREE/name).read_bytes()).hexdigest()!=h]
 receipt={'head':HEAD,'case':args.case,'error':error,'elapsed_seconds':time.monotonic()-started,'source_changes':changed,'temporary_run_removed':not run.exists(),'results':str(output),'nice':os.getpriority(os.PRIO_PROCESS,0)}
 (output/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
 print(json.dumps(receipt));return 1 if error or changed else 0
if __name__=='__main__':raise SystemExit(main())
