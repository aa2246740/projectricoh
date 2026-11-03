"""Clean owned Scratch, seal the delivered repair and independently reread hashes."""
import datetime,hashlib,json,os,plistlib,shutil,subprocess,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
PARENT=HERE.parent
FAST=ROOT/'tools/gxr_emulator_fast/fix_r1'
TEMP=Path('/Volumes/Workspace/Scratch/tmp/projectricoh/emulator-fast-fix-r1')


def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(4<<20),b''):h.update(block)
    return h.hexdigest()


def processes():
    raw=subprocess.run(['ps','-axo','pid,ppid,ni,etime,state,command'],capture_output=True,text=True,check=True,timeout=10).stdout
    rows=[]
    for line in raw.splitlines()[1:]:
        parts=line.split(None,5)
        if len(parts)==6 and int(parts[0])!=os.getpid() and ('/Python ' in parts[5] or 'python3 ' in parts[5]):
            if 'emulator_fast_r1/fix_r1/' in parts[5]:rows.append(line)
    return rows


def main():
    assert os.getpriority(os.PRIO_PROCESS,0)>=15
    evidence=json.loads((HERE/'runs/final-evidence.json').read_text());assert evidence['status']=='PASS'
    disk=plistlib.loads(subprocess.run(['diskutil','info','-plist','/Volumes/Workspace'],capture_output=True,check=True,timeout=20).stdout)
    assert disk['VolumeUUID']=='14BE04EB-AF49-497E-B36A-B078B2F7C5E8' and disk['FilesystemType']=='apfs' and disk['WritableVolume']
    assert not processes(),processes()
    assert not TEMP.is_symlink() and TEMP.resolve()==TEMP
    if TEMP.exists():shutil.rmtree(TEMP)
    assert not TEMP.exists()
    cleanup=dict(status='PASS',when=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                 scratch=str(TEMP),scratch_removed=True,remaining_task_processes=processes(),
                 volume_uuid=disk['VolumeUUID'],library_sha256=evidence['library_sha256'],
                 old_entry_replaced=False,git_write_commands=False,physical_media_access=False,subagents=False)
    assert not cleanup['remaining_task_processes']
    (HERE/'runs/cleanup.json').write_text(json.dumps(cleanup,indent=2)+'\n')
    speeds=evidence['workloads']
    footer='速度为 MAIN '+f"{speeds['main']['speedup']:.2f}"+' 倍、BOOT_RUN '+f"{speeds['boot']['speedup']:.2f}"+' 倍、恢复确认页 '+f"{speeds['recovery']['speedup']:.2f}"+' 倍；本轮五个 P1 所需等价证据齐全，可以交复审；指定 Scratch 已删除，无本任务残留计算进程。\n'
    for path in (PARENT/'REPORT.md',HERE/'REPORT.md'):
        with path.open('a') as stream:stream.write('\n'+footer)
    (HERE/'RUN_STATE.md').write_text('# 修复轮交付状态\n\n'+cleanup['when']+'。最终候选已完成验收并可交修复复审，原入口未替换。\n\n'+footer+'\n最终源码与库身份见 runs/delivery-candidate.json；验收汇总见 runs/final-evidence.json；清理与独立哈希复核见 runs/cleanup.json 和 runs/checksums-verified.json。开发、中止和历史运行不计入最终结论。\n')
    with (PARENT/'PROGRESS.md').open('a') as stream:
        stream.write('\n'+cleanup['when']+'。修复轮收尾。'+footer)
    with (FAST/'CHANGES.md').open('a') as stream:
        stream.write('\n## 2026-11-03：五个 P1 修复候选\n\n完整调度链、设备绑定、公开可变引用、数值范围与实际模型定义检查已补齐。原生执行和只读快照收集分别检查容器借用；未知状态回到 Python 设备执行。快照身份直接绑定实际修正与运行期定义。原入口保留，完整新证据见 research/emulator_fast_r1/REPORT.md。\n')
    legacy=json.loads((HERE/'runs/restart-environment.json').read_text())['legacy_entry_files']
    assert all(sha(ROOT/row['path'])==row['sha256'] for row in legacy)
    manifests={FAST/'SHA256SUMS',HERE/'SHA256SUMS',PARENT/'SHA256SUMS'}
    verification=HERE/'runs/checksums-verified.json'
    policy=dict(scope='Repair candidate, repair receipts and mutable parent REPORT/PROGRESS only.',
                legacy_report='research/emulator_fast_r1/fix_r1/prior/REPORT.md',
                legacy_manifest='research/emulator_fast_r1/fix_r1/prior/SHA256SUMS',
                exclusions=[str(p.relative_to(ROOT)) for p in sorted(manifests|{verification})],
                reason='Live manifests and the verification receipt are excluded to avoid self-reference.')
    (HERE/'runs/manifest-policy.json').write_text(json.dumps(policy,indent=2)+'\n')
    paths=set()
    for base in (FAST,HERE):
        paths.update(p for p in base.rglob('*') if p.is_file() and p not in manifests and p!=verification)
    paths.update((PARENT/'REPORT.md',PARENT/'PROGRESS.md'))
    rows=[]
    for index,path in enumerate(sorted(paths),1):
        rows.append((path,sha(path)))
        if index%2000==0:print(json.dumps(dict(phase='hash',files=index)),flush=True)
    for path in sorted(manifests):
        chosen=[row for row in rows if path!=FAST/'SHA256SUMS' or row[0].is_relative_to(FAST)]
        path.write_text(''.join(digest+'  '+str(file.relative_to(ROOT))+'\n' for file,digest in chosen))
    for index,(path,digest) in enumerate(rows,1):
        assert sha(path)==digest,path
        if index%2000==0:print(json.dumps(dict(phase='verify',files=index)),flush=True)
    result=dict(status='PASS',files=len(rows),scratch_removed=not TEMP.exists(),remaining_task_processes=processes(),
                manifests=[dict(path=str(p.relative_to(ROOT)),sha256=sha(p)) for p in sorted(manifests)])
    assert not result['remaining_task_processes']
    verification.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result),flush=True)


if __name__=='__main__':main()
