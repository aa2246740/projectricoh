#!/usr/bin/python3
"""Verify frozen inputs, remove this task's scratch, and write the final manifest."""
import hashlib
import json
import os
from pathlib import Path
import plistlib
import shutil
import subprocess
import time

ROOT=Path(__file__).resolve().parents[2]
HERE=ROOT/'research/v310_window'
PROTO=ROOT/'firmware/resident_v310_proto'
TEMP=Path('/Volumes/Workspace/Scratch/tmp/projectricoh/v310-window-r1')


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    subprocess.run(['/bin/df','-h','/Volumes/Workspace'],check=True)
    info=plistlib.loads(subprocess.check_output(['/usr/sbin/diskutil','info','-plist','/Volumes/Workspace']))
    assert info['VolumeUUID']=='14BE04EB-AF49-497E-B36A-B078B2F7C5E8'
    assert info['FilesystemType']=='apfs' and info['WritableVolume'] and info['WritableMedia']
    active=[]
    for line in subprocess.check_output(['/bin/ps','-axo','pid=,comm=,args='],text=True).splitlines():
        parts=line.strip().split(None,2)
        if len(parts)<3:continue
        pid,command,args=parts
        if int(pid)==os.getpid() or 'python' not in command.lower():continue
        if 'research/v310_window/' in args and '.py' in args:active.append(int(pid))
    assert not active,('task processes still running',active)
    frozen=json.loads((HERE/'input_receipt.json').read_text())
    differences=[name for name,value in frozen.items()if sha(ROOT/name)!=value['sha256']]
    assert not differences,differences
    baseline=json.loads((HERE/'options/baseline/measurement.json').read_text())
    original_artifacts={'firmware/resident_v39/local/resident/build/resident.bin':baseline['resident_sha256'],
                        'firmware/resident_v39/local/resident/build/resident.elf':baseline['elf_sha256']}
    for name,value in original_artifacts.items():assert sha(ROOT/name)==value,name
    checks=json.loads((HERE/'evidence/checks.json').read_text())
    assert checks['equivalence_acceptance']=='INCOMPLETE' and not checks['cold_standby_pass']
    assert (HERE/'REPORT.md').read_text().splitlines()[0]=='需机主决定'
    source=PROTO/'options/neutral/resident'
    shutil.copytree(source,PROTO/'resident',dirs_exist_ok=True)
    wrapper=('#!/usr/bin/python3\n"""Build the retained two-IROM-source research candidate."""\n'
             'from pathlib import Path\nimport runpy,sys\n'
             'root=Path(__file__).resolve().parents[3]\n'
             'entry=root/"research/v310_window/rebuild.py"\n'
             'sys.argv=[str(entry),"--profile","neutral",*sys.argv[1:]]\n'
             'runpy.run_path(str(entry),run_name="__main__")\n')
    (PROTO/'resident/build.py').write_text(wrapper)
    for path in source.iterdir():
        if path.is_file() and path.name!='build.py':assert path.read_bytes()==(PROTO/'resident'/path.name).read_bytes()
    profile=json.loads((HERE/'options/neutral/measurement.json').read_text())
    trust=json.loads((HERE/'options/neutral/trust.json').read_text())
    default=dict(name='neutral',accepted=False,cold_standby='NOT_CLOSED',
                 code_bytes=profile['code_bytes'],free_bytes=profile['free_above_margin'],
                 resident_sha256=profile['resident_sha256'],elf_sha256=profile['elf_sha256'],
                 resident_build_id=trust['resident_build_id'],resident_abi_id=trust['resident_abi_id'],
                 behavior_changes_adopted=False)
    (PROTO/'default-profile.json').write_text(json.dumps(default,indent=2)+'\n')
    removed_objects=0
    for folder in (HERE/'options').iterdir():
        if not folder.is_dir():continue
        for path in folder.rglob('*.o'):
            path.unlink();removed_objects+=1
    assert not TEMP.is_symlink()
    if TEMP.exists():shutil.rmtree(TEMP)
    assert not TEMP.exists()
    extra_paths=['firmware/package_v39_g153_test/local/SD_ROOT/GXRCE.DAT',
                 'firmware/engine_v62_g153/candidate/local/full-r13/engine.elf',
                 'tools/native_harness_c/local/ccore/build.json',
                 'tools/gxr_emulator_batch/build/libgxr_m32r.dylib']
    extra={name:sha(ROOT/name)for name in extra_paths}
    fixture=json.loads((HERE/'evidence/fixture-neutral.json').read_text())
    assert extra[extra_paths[0]]==fixture['original_dat_sha256']
    assert extra[extra_paths[1]]==fixture['engine_sha256']
    receipt=dict(status='research complete; equivalence gate remains open',
                 window_verdict='需机主决定',input_files=len(frozen),input_differences=differences,
                 extra_inputs=extra,scratch=str(TEMP),scratch_removed=True,
                 original_artifacts=original_artifacts,
                 removed_intermediate_objects=removed_objects,default_profile=default,
                 body_images_retained=False,behavior_changes_adopted=False,
                 ended_utc=time.strftime('%Y-%m-%d %H:%M:%S UTC',time.gmtime()))
    (HERE/'FINAL.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
    progress=(HERE/'PROGRESS.md').read_text()
    if progress.startswith('进行中\n'):progress=progress.replace('进行中\n','已结束：尺寸研究完成，等价验收仍缺普通冷启动待机。\n',1)
    progress+='\n最终核对：冻结输入 '+str(len(frozen))+' 项，差异 0；默认原型保留两个 IROM 来源。\n'
    progress+='所有本轮前台进程已退出，指定 scratch 已删除，中间目标文件已清理。最终时间：'+receipt['ended_utc']+'。\n'
    (HERE/'PROGRESS.md').write_text(progress)
    files=sorted(p for base in [PROTO,HERE]for p in base.rglob('*')if p.is_file() and p.name!='SHA256SUMS')
    manifest=''.join(sha(path)+'  '+str(path.relative_to(ROOT))+'\n'for path in files)
    sums=HERE/'SHA256SUMS';sums.write_text(manifest)
    for line in sums.read_text().splitlines():
        expected,name=line.split('  ',1);assert sha(ROOT/name)==expected,name
    print(json.dumps(dict(status='PASS',manifest_files=len(files),frozen_files=len(frozen),
                          input_differences=0,scratch_removed=True,verdict='需机主决定'),ensure_ascii=False))


if __name__=='__main__':main()
