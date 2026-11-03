"""Seal the final evidence, remove only the private temp tree, and verify hashes."""
import contextlib
import datetime
import hashlib
import io
import json
import os
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
TEMP=Path('/Volumes/Workspace/Scratch/tmp/projectricoh/tweak-memory-r1')
sys.path.insert(0,str(HERE))
from repro_flow import phase


def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()


def processes():
    rows=[]
    raw=subprocess.check_output(['ps','-Ao','pid,ni,command'],text=True)
    for line in raw.splitlines()[1:]:
        fields=line.strip().split(None,2)
        if len(fields)!=3:continue
        pid,priority,command=fields
        program=command.split(' ',1)[0]
        if Path(program).name.lower() not in ('python','python3'):continue
        if int(pid)==os.getpid():continue
        if 'research/tweak_memory_r1/' in command or str(HERE)+'/' in command:
            rows.append(dict(pid=int(pid),nice=int(priority),command=command))
    return rows


def main():
    assert os.getpriority(os.PRIO_PROCESS,0)>=10
    disk=plistlib.loads(subprocess.check_output(['/usr/sbin/diskutil','info','-plist','/Volumes/Workspace']))
    assert disk['VolumeUUID'].upper()=='14BE04EB-AF49-497E-B36A-B078B2F7C5E8'
    assert disk['FilesystemType'].lower()=='apfs' and disk.get('WritableVolume',not disk.get('VolumeReadOnly',False))
    assert os.path.ismount('/Volumes/Workspace') and os.access('/Volumes/Workspace',os.W_OK)
    active=processes();assert not active,('task workers remain',len(active))
    rows=[];sink=io.StringIO()
    checks=[('cache_check.py',['--prefix','p1final-','--name','final-cache-check'],'final-seal-cache'),
        ('increment_static.py',['--name','final-increment-seal'],'final-seal-static'),
        ('source_audit.py',[],'final-seal-sources'),('artifact_audit.py',[],'final-seal-artifacts'),
        ('final_matrix.py',[],'final-seal-matrix')]
    with contextlib.redirect_stdout(sink):
        for script,args,name in checks:phase(script,args,name,rows)
    provenance=[]
    for name in ('p1final-init-r2','p1final-release','p1final-mount-cold1','p1final-mount-cold2','p1final-user-cold1','p1final-zero'):
        path=HERE/'evidence'/(name+'.json')
        if not path.exists():continue
        r=json.loads(path.read_text())
        assert r['library_sha256']=='018a6d9731d54b6b27e6729d4a8903a4cab5b8763a0ce92467ad91e02d2d8c95'
        provenance.append(dict(case=name,library_sha256=r['library_sha256'],source_count=len(r['sources']),receipt_sha256=digest(path)))
    (HERE/'evidence/final-backend-provenance.json').write_text(json.dumps(dict(status='PASS',rows=provenance),indent=2)+'\n')
    assert TEMP.resolve()==TEMP and not TEMP.is_symlink()
    temp_count=sum(1 for p in TEMP.rglob('*') if p.is_file()) if TEMP.exists() else 0
    if TEMP.exists():shutil.rmtree(TEMP)
    active=processes();assert not TEMP.exists() and not active
    cleanup=dict(status='PASS',private_tmp=str(TEMP),removed_files=temp_count,tmp_exists=False,
        task_process_count=len(active),volume_uuid=disk['VolumeUUID'],filesystem=disk['FilesystemType'],
        retained_derived_bytes='research/tweak_memory_r1/local and engine_v67_g155c/candidate/local',
        utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
    (HERE/'evidence/cleanup-final.json').write_text(json.dumps(cleanup,indent=2)+'\n')
    matrix=json.loads((HERE/'evidence/final-matrix.json').read_text())
    groups='\n'.join('- '+r['case']+'：'+r['status']+'，'+str(r['complete_cold_cycles'])+'/'+str(r['required_cycles'])+' 轮。' for r in matrix['groups'])
    progress='有缺陷；本轮收尾结束。\n\n截止 2026-11-03 07:28:28 UTC。\n\n模式 P1：'+matrix['P1_mode_contract']+'。完整 NAND 关机持久化与机主内置 HC BW 根因仍 OPEN。\n\n'+groups+'\n\n同 DAT 零微调记录：'+matrix['same_DAT_zero_record']['status']+'。H52 与移走 DAT 后 HALF/FULL 续接已有独立收据；完整照片未验收。\n\n旧 g154 用户和 Looks 写全零记录；用户为实测，Looks 为同分支静态结论。白平衡不为 9/9 会拒绝预选，但不会清空记录，现场归因仍 OPEN，未新增白平衡运行。\n\nrelease SHA-256 '+matrix['release_DAT_sha256']+'\ntest SHA-256 '+matrix['test_DAT_sha256']+'\n\n私有 TMPDIR 已清理；本任务残留进程为 0。详见 REPORT.md、evidence/final-matrix.json、cleanup-final.json 和 SHA256SUMS。\n'
    (HERE/'PROGRESS.md').write_text(progress)
    log=HERE/'decisions.tsv'
    with log.open('a') as f:
        f.write(datetime.datetime.now(datetime.timezone.utc).isoformat()+'\tclose\t按最终 SHA 汇总，未完成项保留 OPEN\t真实 NAND 未保存成功，不能以声明回放代替\tevidence/final-matrix.json,evidence/cleanup-final.json\t有缺陷；私有临时目录已清理，残留为 0\n')
    with contextlib.redirect_stdout(sink):phase('render_report.py',[],'final-seal-report',rows)
    (HERE/'evidence/final-seal-phases.json').write_text(json.dumps(rows,indent=2)+'\n')
    excluded={HERE/'SHA256SUMS',HERE/'evidence/sha-verification.json'}
    paths=set()
    for directory in (HERE,ROOT/'firmware/engine_v67_g155c',ROOT/'firmware/package_v310_g155c',ROOT/'firmware/package_v310_g155c_test'):
        paths.update(p for p in directory.rglob('*') if p.is_file() and p not in excluded and '__pycache__' not in p.parts)
    parent=json.loads((HERE/'evidence/g155b-source-freeze.json').read_text())
    paths.update(ROOT/name for name in parent)
    frozen=json.loads((HERE/'evidence/final-increment-seal.json').read_text())['frozen_files']
    paths.update(ROOT/r['path'] for r in frozen)
    for name in ('backend.py','devices.py','peripherals.py','storage_run.py','standby_run.py','sdcard.py','build/libgxr_m32r.dylib'):
        paths.add(ROOT/'tools/gxr_emulator_standby'/name)
    for name in ('python_backend.py','backend_api.py','ccore/backend.py'):
        paths.add(ROOT/'tools/native_harness_c'/name)
    manifest=HERE/'SHA256SUMS'
    lines=[]
    for p in sorted(paths):
        relative=str(p.relative_to(ROOT));assert '\n' not in relative
        lines.append(digest(p)+'  '+relative+'\n')
    manifest.write_text(''.join(lines))
    check=subprocess.run(['/usr/bin/shasum','-a','256','-c',str(manifest)],cwd=ROOT,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    verification=dict(status='PASS' if check.returncode==0 else 'OPEN',checked_files=len(lines),returncode=check.returncode,
        manifest_sha256=digest(manifest),output_sha256=hashlib.sha256(check.stdout.encode()).hexdigest(),
        stderr_sha256=hashlib.sha256(check.stderr.encode()).hexdigest(),task_process_count=len(processes()),tmp_exists=TEMP.exists(),
        utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        exclusions=['SHA256SUMS','evidence/sha-verification.json'])
    (HERE/'evidence/sha-verification.json').write_text(json.dumps(verification,indent=2)+'\n')
    assert check.returncode==0 and verification['task_process_count']==0 and not verification['tmp_exists']
    assert datetime.datetime.now(datetime.timezone.utc)<datetime.datetime(2026,11,3,7,28,28,tzinfo=datetime.timezone.utc)
    print(json.dumps(dict(verdict='有缺陷',P1=matrix['P1_mode_contract'],verified_files=len(lines),
        manifest_sha256=verification['manifest_sha256'],cleanup='PASS',remaining_processes=0,
        release_DAT_sha256=matrix['release_DAT_sha256'],test_DAT_sha256=matrix['test_DAT_sha256']),ensure_ascii=False))


if __name__=='__main__':main()
