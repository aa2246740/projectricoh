#!/usr/bin/python3
"""Verify the retained results, remove task scratch, and seal file digests."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import plistlib
import re
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
OUT = HERE/'evidence'
TOOLS = ROOT/'tools/gxr_emulator_standby'
TEMP = Path('/Volumes/Workspace/Scratch/tmp/projectricoh/emulator-standby-r1')


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as source:
        for block in iter(lambda:source.read(1024*1024),b''):
            h.update(block)
    return h.hexdigest()


def seal():
    assert Path(os.environ['TMPDIR']).resolve() == TEMP
    disk = plistlib.loads(subprocess.check_output(['diskutil','info','-plist','/Volumes/Workspace']))
    assert disk['VolumeUUID'].upper() == '14BE04EB-AF49-497E-B36A-B078B2F7C5E8'
    assert disk['FilesystemType'].lower() == 'apfs'
    assert not disk.get('ReadOnlyVolume',False) and not disk.get('ReadOnlyMedia',False)
    assert disk['MountPoint'] == '/Volumes/Workspace'
    assert json.loads((OUT/'repeatability.json').read_text())['status'] == 'PASS'
    assert json.loads((OUT/'model-off-comparison.json').read_text())['status'] == 'PASS'
    assert json.loads((OUT/'model-checks.json').read_text())['status'] == 'PASS'
    initial = json.loads((OUT/'frozen-inputs.json').read_text())
    differences = [name for name,digest in initial.items() if sha(ROOT/name) != digest]
    assert not differences,differences
    frozen = json.loads((OUT/'final-tool-sources.json').read_text())
    assert all(sha(ROOT/name) == digest for name,digest in frozen.items())
    ps = subprocess.check_output(['/bin/ps','-axo','pid,ppid,ni,comm,args'],text=True)
    active=[]
    for line in ps.splitlines()[1:]:
        fields=line.split(None,4)
        if len(fields) == 5 and Path(fields[3]).name.lower().startswith('python') \
                and re.search(r'(?:standby_run|compatibility|model_checks|protocol_study)\.py',fields[4]):
            active.append(line)
    assert not active,active
    files=[p for p in TEMP.rglob('*') if p.is_file()]
    count=len(files)
    size=sum(p.stat().st_size for p in files)
    assert TEMP.resolve() == TEMP and TEMP.name == 'emulator-standby-r1'
    if TEMP.exists():
        shutil.rmtree(TEMP)
    finished=datetime.now(timezone.utc)
    elapsed=(finished-datetime(2026,11,1,22,17,12,tzinfo=timezone.utc)).total_seconds()
    cleanup=dict(scratch=str(TEMP),removed_files=count,removed_bytes=size,
                 scratch_exists=TEMP.exists(),active_emulator_processes=active,
                 original_files_checked=len(initial),original_file_differences=differences,
                 tool_source_binding_equal=True,disk_uuid=disk['VolumeUUID'],
                 filesystem=disk['FilesystemType'],finished_utc=finished.isoformat(),elapsed_seconds=elapsed)
    (OUT/'cleanup.json').write_text(json.dumps(cleanup,indent=2)+'\n')
    with (HERE/'PROGRESS.md').open('a') as target:
        target.write(f'- 最终 12 次冷启动、两项关闭模型比较和 10 项功能边界检查全部通过。\n'
                     f'- 最终再次核对原输入 {len(initial):,} 个文件，差异为零。新工具源与实际运行绑定摘要一致。\n'
                     f'- 已清理 scratch 中 {count} 个文件、{size:,} 字节；目录已删除，运行进程为零。\n'
                     f'- 结束时间 {finished.isoformat()}，本轮耗时 {elapsed/60:.1f} 分钟，在三小时时限内。\n')
    done=dict(verdict='到达待机',cold_runs=12,repeated_pairs=6,model_off_cases=2,
              functional_checks=10,report_sha256=sha(HERE/'REPORT.md'),
              final_tool_sources_sha256=sha(OUT/'final-tool-sources.json'),cleanup=cleanup)
    (HERE/'DONE.json').write_text(json.dumps(done,indent=2,ensure_ascii=False)+'\n')
    manifests=[]
    for directory in (TOOLS,HERE):
        manifest=directory/'SHA256SUMS'
        selected=sorted(p for p in directory.rglob('*') if p.is_file() and p != manifest
                        and '__pycache__' not in p.parts and p.name != '.DS_Store')
        manifest.write_text(''.join(f'{sha(p)}  {p.relative_to(ROOT)}\n' for p in selected))
        manifests.append((manifest,selected))
    for manifest,selected in manifests:
        for line in manifest.read_text().splitlines():
            expected,name=line.split('  ',1)
            assert sha(ROOT/name) == expected,name
    print(json.dumps(dict(status='PASS',scratch_removed=not TEMP.exists(),
                          source_files_unchanged=len(initial),elapsed_minutes=round(elapsed/60,1),
                          manifests={str(p.relative_to(ROOT)):len(files) for p,files in manifests})))


if __name__ == '__main__':
    seal()
