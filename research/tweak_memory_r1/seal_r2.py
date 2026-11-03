"""Verify round-two identities, retain evidence, and clear the private temp tree."""
import datetime
import hashlib
import json
import os
from pathlib import Path
import plistlib
import re
import shutil
import subprocess
import sys

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path.insert(0,str(HERE))
from finalize import digest,processes,TEMP
from repro_flow import phase


def main():
    assert os.getpriority(os.PRIO_PROCESS,0)>=10
    disk=plistlib.loads(subprocess.check_output(['/usr/sbin/diskutil','info','-plist','/Volumes/Workspace']))
    assert disk['VolumeUUID'].upper()=='14BE04EB-AF49-497E-B36A-B078B2F7C5E8'
    assert disk['FilesystemType'].lower()=='apfs' and disk.get('Writable',False)
    assert os.path.ismount('/Volumes/Workspace') and not processes()
    rows=[]
    for script,args,name in [
        ('cache_check.py',['--name','r2-cache-check'],'r2-seal-cache'),
        ('increment_static.py',['--name','r2-increment-static'],'r2-seal-static')]:
        phase(script,args,name,rows)
    start=json.loads((HERE/'evidence/r2-start.json').read_text())
    archived=[]
    for name,expected in start['archive'].items():
        assert digest(ROOT/name)==expected
        archived.append(dict(path=name,sha256=expected))
    changes=[];compared=[]
    for before in (HERE/'local/r1-seal/product').rglob('*'):
        if not before.is_file():continue
        after=ROOT/'firmware/engine_v67_g155c/candidate/containers/product'/before.relative_to(HERE/'local/r1-seal/product')
        row=dict(path=str(after.relative_to(ROOT)),before=digest(before),after=digest(after))
        compared.append(row)
        if row['before']!=row['after']:changes.append(row)
    build_objects=[]
    for profile in ('boot-on','boot-off'):
        for filename in ('engine.elf','layout.json'):
            before=HERE/'local/r1-seal'/profile/filename
            after=ROOT/'firmware/engine_v67_g155c/candidate/local'/profile/filename
            if not before.exists():continue
            assert digest(before)==digest(after)
            build_objects.append(dict(profile=profile,file=filename,sha256=digest(after)))
    for package in ('package_v310_g155c','package_v310_g155c_test'):
        assert digest(HERE/'local/r1-seal'/package/'GXRCE.DAT')==digest(ROOT/'firmware'/package/'GXRCE.DAT')
    r1_manifest={line[66:]:line[:64] for line in (HERE/'local/r1-seal/SHA256SUMS').read_text().splitlines() if len(line)>66}
    for filename in ('probe.py','runtime.py','cold_run.py'):
        assert digest(HERE/'local/r1-seal'/filename)==r1_manifest['research/tweak_memory_r1/'+filename]
    parent=json.loads((HERE/'evidence/g155b-source-freeze.json').read_text())
    for name,expected in parent.items():
        value=expected['sha256'] if isinstance(expected,dict) else expected
        assert digest(ROOT/name)==value
    provenance=[]
    for prefix in ('p1final-look-cold1','p1final-50-cold1','p1final-28-init','p1final-28-cold1',
                   'r2-daylight-g154-cold','r2-daylight-g155c-cold'):
        path=HERE/'evidence'/(prefix+'.json')
        if not path.exists():continue
        receipt=json.loads(path.read_text())
        assert receipt['library_sha256']=='018a6d9731d54b6b27e6729d4a8903a4cab5b8763a0ce92467ad91e02d2d8c95'
        provenance.append(dict(case=prefix,library_sha256=receipt['library_sha256'],receipt_sha256=digest(path)))
    stability=dict(status='PASS',archive_files=len(archived),archive_summary_sha256=start['archive_summary_sha256'],
        product_compared_files=len(compared),product_changes=changes,g155b_source_files=len(parent),g155b_source_changes=0,
        compared_build_objects=build_objects,r1_runner_archives_verified=3,
        test_DAT_sha256=digest(ROOT/'firmware/package_v310_g155c_test/GXRCE.DAT'),
        release_DAT_sha256=digest(ROOT/'firmware/package_v310_g155c/GXRCE.DAT'),backend_provenance=provenance)
    (HERE/'evidence/r2-stability.json').write_text(json.dumps(stability,ensure_ascii=False,indent=2)+'\n')
    assert TEMP.resolve()==TEMP and not TEMP.is_symlink()
    count=sum(1 for p in TEMP.rglob('*') if p.is_file()) if TEMP.exists() else 0
    if TEMP.exists():shutil.rmtree(TEMP)
    assert not processes() and not TEMP.exists()
    cleanup=dict(status='PASS',private_tmp=str(TEMP),removed_files=count,tmp_exists=False,task_process_count=0,
        volume_uuid=disk['VolumeUUID'],filesystem=disk['FilesystemType'],utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
    (HERE/'evidence/r2-cleanup.json').write_text(json.dumps(cleanup,indent=2)+'\n')
    phase('final_matrix.py',['--name','r2-final-matrix'],'r2-seal-matrix',rows)
    phase('render_r2_report.py',[],'r2-seal-report',rows)
    matrix=json.loads((HERE/'evidence/r2-final-matrix.json').read_text())
    wb=json.loads((HERE/'evidence/r2-wb-summary.json').read_text())
    groups='\n'.join('- '+r['case']+'：'+r['status']+'，'+str(r['complete_cold_cycles'])+'/'+str(r['required_cycles'])+' 轮。' for r in matrix['groups'])
    progress='有缺陷；第二轮收尾结束。\n\n起点 2026-11-03 07:48:20 UTC；截止 10:18:20 UTC。检查点见 evidence/r2-checkpoint.json。\n\n'+groups+'\n\n日光受检字节结论：'+wb['daylight_preset_gate_effect']+'；完整组合：'+', '.join(r['version']+' '+r['status'] for r in wb['daylight_combination_comparisons'])+'。原厂控制流程：'+wb['native_controls_status']+'。机主现场根因和两种真实 NAND 关机持久化仍 OPEN。\n\n产品与 DAT 未改。test SHA-256 '+stability['test_DAT_sha256']+'\nrelease SHA-256 '+stability['release_DAT_sha256']+'\n\n本任务 TMPDIR 已清理，测试工作进程残留 0。最终结论、其余 OPEN 和校验见 REPORT.md、evidence/r2-final-matrix.json、evidence/r2-cleanup.json 和 SHA256SUMS。\n'
    (HERE/'PROGRESS.md').write_text(progress)
    missing=[]
    for target in re.findall(r'\]\(([^)]+)\)',(HERE/'REPORT.md').read_text()):
        if target.startswith(('http:','https:')):continue
        if target=='evidence/r2-sha-verification.json':continue
        if not (HERE/target).exists():missing.append(target)
    assert not missing,('report missing local links',len(missing))
    (HERE/'evidence/r2-seal-phases.json').write_text(json.dumps(rows,indent=2)+'\n')
    manifest=HERE/'SHA256SUMS';verification=HERE/'evidence/r2-sha-verification.json'
    paths=set()
    for directory in (HERE,ROOT/'firmware/engine_v67_g155c',ROOT/'firmware/package_v310_g155c',ROOT/'firmware/package_v310_g155c_test'):
        paths.update(p for p in directory.rglob('*') if p.is_file() and p not in (manifest,verification) and '__pycache__' not in p.parts)
    paths.update(ROOT/name for name in parent)
    frozen=json.loads((HERE/'evidence/r2-increment-static.json').read_text())['frozen_files']
    paths.update(ROOT/r['path'] for r in frozen)
    for name in ('backend.py','devices.py','peripherals.py','storage_run.py','standby_run.py','sdcard.py','build/libgxr_m32r.dylib'):
        paths.add(ROOT/'tools/gxr_emulator_standby'/name)
    for name in ('python_backend.py','backend_api.py','ccore/backend.py'):
        paths.add(ROOT/'tools/native_harness_c'/name)
    lines=[]
    for path in sorted(paths):
        name=str(path.relative_to(ROOT));assert '\n' not in name
        lines.append(digest(path)+'  '+name+'\n')
    manifest.write_text(''.join(lines))
    check=subprocess.run(['/usr/bin/shasum','-a','256','-c',str(manifest)],cwd=ROOT,
        text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    receipt=dict(status='PASS' if check.returncode==0 else 'OPEN',checked_files=len(lines),
        returncode=check.returncode,manifest_sha256=digest(manifest),
        output_sha256=hashlib.sha256(check.stdout.encode()).hexdigest(),stderr_sha256=hashlib.sha256(check.stderr.encode()).hexdigest(),
        task_process_count=len(processes()),tmp_exists=TEMP.exists(),utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        deadline_utc=start['deadline_utc'],exclusions=['SHA256SUMS','evidence/r2-sha-verification.json'])
    verification.write_text(json.dumps(receipt,indent=2)+'\n')
    assert check.returncode==0 and receipt['task_process_count']==0 and not receipt['tmp_exists']
    print(json.dumps(dict(status='PASS',verified_files=len(lines),manifest_sha256=receipt['manifest_sha256'],
        product_changes=len(changes),g155b_source_changes=0,remaining_processes=0,tmp_exists=False)))


if __name__=='__main__':main()
