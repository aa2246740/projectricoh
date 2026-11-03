"""Seal artifacts, remove the task's temporary directory, and check every hash."""
import datetime,hashlib,json,os,plistlib,signal,subprocess,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from safety import enable,HERE,FAST,ROOT,TEMP
enable();signal.alarm(600)


def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(4*1024*1024),b''):h.update(block)
    return h.hexdigest()


def main():
    assert os.getpriority(os.PRIO_PROCESS,0)>=15
    volume=plistlib.loads(subprocess.run(['diskutil','info','-plist','/Volumes/Workspace'],capture_output=True,check=True,timeout=15).stdout)
    assert volume['VolumeUUID' if 'VolumeUUID' in volume else 'DiskUUID']=='14BE04EB-AF49-497E-B36A-B078B2F7C5E8'
    assert volume['MountPoint']=='/Volumes/Workspace' and volume['FilesystemType']=='apfs'
    listing=subprocess.run(['ps','-Ao','pid,ni,etime,args'],capture_output=True,text=True,check=True,timeout=10).stdout
    ours=[]
    for line in listing.splitlines()[1:]:
        fields=line.strip().split(None,3)
        if len(fields)!=4:continue
        if int(fields[0])!=os.getpid() and any(marker in fields[3] for marker in ('research/emulator_fast_r1/','tools/gxr_emulator_fast/')):ours.append(line.strip())
    assert not ours,ours
    assert TEMP==Path('/Volumes/Workspace/Scratch/tmp/projectricoh/emulator-fast-r1') and TEMP.resolve()==TEMP
    assert (HERE/'runs/final-evidence.json').is_file()
    began=time.perf_counter()
    subprocess.run(['/bin/rm','-rf','--',str(TEMP)],check=True,timeout=120)
    assert not TEMP.exists()
    now=datetime.datetime.now(datetime.timezone.utc).isoformat()
    evidence=json.loads((HERE/'runs/final-evidence.json').read_text())
    progress=HERE/'PROGRESS.md'
    progress.write_text(progress.read_text()+'\n'+now+'。收尾：三项配对倍数 '+str({k:round(v['paired_speedup'],2) for k,v in evidence['performance'].items()})+'；所有配对检查点逐位一致。默认恢复终点 1,859,053,607 步、全状态和 NAND 与原批量连续运行相同；原生含快照 341.650 秒，完整成功恢复仍未闭合。四修正六组全状态差分、快照、串并行、g145、变异及历史钩子反例通过；M2c 保留 20/21，宿主停点仍有一次兼容回调。指定临时目录已删除，未发现本任务残留计算进程；生成并独立重读 SHA256SUMS。\n')
    record=dict(finished_utc=now,temporary_directory=str(TEMP),temporary_directory_exists=False,
                own_processes_remaining=ours,nice=os.getpriority(os.PRIO_PROCESS,0),
                volume_uuid='14BE04EB-AF49-497E-B36A-B078B2F7C5E8',
                free_space=subprocess.run(['df','-h','/Volumes/Workspace'],capture_output=True,text=True,check=True,timeout=10).stdout,
                cleanup_seconds=time.perf_counter()-began,elapsed_wall_seconds=time.time()-json.loads((HERE/'frozen-inputs.json').read_text())['started'],
                acceptance_complete=False,review_ready=False)
    (HERE/'runs/cleanup.json').write_text(json.dumps(record,indent=2)+'\n')
    manifest=HERE/'SHA256SUMS'
    files=sorted(path for root in (FAST,HERE) for path in root.rglob('*') if path.is_file() and path!=manifest)
    lines=[sha(path)+'  '+str(path.relative_to(ROOT)) for path in files]
    manifest.write_text('\n'.join(lines)+'\n')
    # A separate read pass verifies the final bytes, including the cleanup receipt.
    for line in manifest.read_text().splitlines():
        expected,name=line.split('  ',1);assert sha(ROOT/name)==expected,name
    assert not TEMP.exists()
    print(json.dumps(dict(cleaned=True,manifest_entries=len(lines),all_hashes_verified=True,
                         manifest_sha256=sha(manifest),seconds=time.perf_counter()-began)))


if __name__=='__main__':main()
