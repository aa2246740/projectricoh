"""Offline run boundaries restricted to speedlab and the declared temporary root."""
import hashlib,json,os,plistlib,subprocess,sys,tempfile
from pathlib import Path
ROOT=Path('/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh')
HERE=Path(__file__).resolve().parent
TEMP=Path('/Volumes/Workspace/Scratch/tmp/projectricoh/review-cswitch')
def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1048576),b''):h.update(block)
    return h.hexdigest()
def emit(path,value):
    Path(path).parent.mkdir(parents=True,exist_ok=True)
    Path(path).write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n')
def enable():
    assert os.getpriority(os.PRIO_PROCESS,0)>=15
    mounted=plistlib.loads(subprocess.check_output(['/usr/sbin/diskutil','info','-plist','/Volumes/Workspace']))
    assert mounted['VolumeUUID']=='14BE04EB-AF49-497E-B36A-B078B2F7C5E8' and mounted['WritableVolume'] and mounted['FilesystemType']=='apfs'
    TEMP.mkdir(parents=True,exist_ok=True)
    os.environ.update(TMPDIR=str(TEMP),PYTHONDONTWRITEBYTECODE='1',GIT_OPTIONAL_LOCKS='0',CLANG_MODULE_CACHE_PATH=str(TEMP/'clang-modules'))
    tempfile.tempdir=str(TEMP)
    def check(path):
        if path is None or isinstance(path,int):return
        target=Path(os.fsdecode(path)).resolve()
        if target==Path('/dev/null'):return
        if not (target.is_relative_to(Path('/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/review_harness_c_switch')) or target.is_relative_to(TEMP)):raise PermissionError('write outside speedlab: '+str(target))
    def audit(event,args):
        if event=='open':
            path,mode,flags=args
            if not isinstance(path,int):
                p=Path(os.fsdecode(path)).absolute()
                if str(p).startswith('/Volumes/') and not p.is_relative_to(Path('/Volumes/Workspace')):raise PermissionError('media outside run')
            if mode and any(c in mode for c in 'wax+') or (flags or 0)&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND):check(path)
        elif event in ('os.mkdir','os.remove','os.rmdir','os.utime','os.chmod','os.truncate'):check(args[0])
        elif event in ('os.rename','os.link','os.symlink'):check(args[0]);check(args[1])
        elif event.startswith('socket.') and event!='socket.__new__':raise PermissionError('network disabled')
    sys.addaudithook(audit)
