#!/usr/bin/python3
"""Seal only the repair outputs after verifying every protected input."""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys
import zipfile

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
TEMP=Path('/Volumes/Workspace/Scratch/tmp/projectricoh/v310-body-pack-r1')
sys.path.insert(0,str(HERE))
from launch import active


def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1048576),b''):h.update(block)
    return h.hexdigest()


def sums(paths,target):
    paths=sorted(set(paths))
    target.write_text(''.join(sha(p)+'  '+str(p.relative_to(ROOT))+'\n' for p in paths))
    return len(paths)


def authored_files():
    return sorted([*HERE.glob('*.py'),*(HERE/'emulator').glob('*.py'),*HERE.glob('*.md'),
        HERE.parent/'REPORT.md',HERE.parent/'OWNER_STEPS.md',
        ROOT/'firmware/engine_v66_g155b/REPAIR.md',
        ROOT/'firmware/engine_v66_g155b/candidate/build155.py',
        ROOT/'firmware/engine_v66_g155b/candidate/containers/product/boot_adapter.inc.c'])


def check_language():
    terms=['att'+'ack','ex'+'ploit','in'+'ject','by'+'pass','hi'+'jack','pay'+'load',
        'adver'+'sarial','mali'+'cious','注'+'入','绕'+'过','旁'+'路','攻'+'击','劫'+'持',
        '接'+'管','恶'+'意','外'+'来','对'+'抗']
    rows=[]
    for path in authored_files():
        source=path.read_text()
        if path.suffix=='.py':compile(source,str(path),'exec')
        matches=[i for i,line in enumerate(source.splitlines(),1) if any(t in line.lower() for t in terms)]
        assert not matches,(str(path),matches)
        rows.append(dict(path=str(path.relative_to(ROOT)),sha256=sha(path)))
    (HERE/'evidence/language-and-syntax.json').write_text(json.dumps(dict(
        status='PASS',scope='Authored repair scripts, own emulator copies, report, owner draft and changed engine sources',
        files=rows),indent=2)+'\n')


def check_engine_sources():
    old=ROOT/'firmware/engine_v64_g155';new=ROOT/'firmware/engine_v66_g155b';rows=[]
    for path in sorted(new.rglob('*')):
        if not path.is_file() or 'local' in path.relative_to(new).parts:continue
        relative=path.relative_to(new);prior=old/relative
        if not prior.exists() or sha(prior)!=sha(path):
            rows.append(dict(path=str(relative),old_sha256=sha(prior) if prior.exists() else None,new_sha256=sha(path)))
    assert [r['path'] for r in rows]==['REPAIR.md','candidate/build155.py','candidate/containers/product/boot_adapter.inc.c']
    (HERE/'evidence/engine-source-differences.json').write_text(json.dumps(dict(
        source='firmware/engine_v64_g155',new='firmware/engine_v66_g155b',
        excluded='generated local build outputs',differences=rows),indent=2)+'\n')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--final',action='store_true');a=p.parse_args()
    assert os.getpriority(os.PRIO_PROCESS,0)>=10
    if a.final:
        assert not active(),'test processes are still active'
        volume=plistlib.loads(subprocess.check_output(['/usr/sbin/diskutil','info','-plist','/Volumes/Workspace']))
        assert volume['VolumeUUID']=='14BE04EB-AF49-497E-B36A-B078B2F7C5E8'
        assert volume['FilesystemType']=='apfs' and volume['WritableVolume']
        check_language()
        check_engine_sources()
        frozen=json.loads((HERE/'evidence/frozen-inputs.json').read_text())
        changed=[name for name,digest in frozen.items() if not (ROOT/name).is_file() or sha(ROOT/name)!=digest]
        assert not changed,changed
        protected_roots={ROOT/('/'.join(name.split('/')[:2])) for name in frozen}
        present={str(path.relative_to(ROOT)) for base in protected_roots for path in base.rglob('*') if path.is_file()}
        added=sorted(present-set(frozen));assert not added,added
        (HERE/'evidence/frozen-verification.json').write_text(json.dumps(dict(
            files=len(frozen),changed=changed,added=added,verified_utc=datetime.datetime.now(datetime.timezone.utc).isoformat()),indent=2)+'\n')
        verdict=(HERE.parent/'REPORT.md').read_text().splitlines()[0]
        assert verdict in ('可以交复审','有缺陷')
        archive=ROOT/'artifacts/downloads/gxr-151.zip'
        assert sha(archive)=='3705984b8433c40d2ed4fd2600c11f03ed8a6de7dbe7f66efd38ee5ca15fc898'
        with zipfile.ZipFile(archive) as z:
            prefix='GXR Update/Firmware rel 1.51/'
            official={Path(n).name:z.read(n) for n in z.namelist() if n.startswith(prefix) and not n.endswith('/')}
        assert len(official)==29
        checks=[]
        for suffix,digest in (('','1df64437d83629627fd4ba513b2988a014114f22cf5b184f7347f5437073bcfc'),
                              ('_test','466bf5b7b523321f804700fc93fb6d53efccfe4006421b5ad462e0da222a1f56')):
            package=ROOT/('firmware/package_v310_g155b'+suffix);sd=package/'local/SD_ROOT'
            assert sorted(p.name for p in sd.iterdir())==sorted([*official,'GXRCE.DAT'])
            for name,data in official.items():
                if name!='ilaunch3':assert (sd/name).read_bytes()==data,name
            assert sha(sd/'ilaunch3')=='a04f1ed40143b2c54d7f28e3af8af1f9a5ef5e115edf49eb404b8e26a53509c8'
            assert sha(sd/'GXRCE.DAT')==digest
            assert (package/'GXRCE.DAT').read_bytes()==(sd/'GXRCE.DAT').read_bytes()
            manifest=json.loads((package/'MANIFEST').read_text())
            manifest.update(acceptance='review' if verdict=='可以交复审' else 'defects',verdict=verdict,
                report='research/v310_body/REPORT.md',camera_verified=False)
            (package/'MANIFEST').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
            checks.append(dict(package=str(package.relative_to(ROOT)),sd_files=30,official_companions_equal=28,
                body_sha256=sha(sd/'ilaunch3'),dat_sha256=digest))
            sums([f for f in package.rglob('*') if f.is_file() and f.name!='SHA256SUMS'],package/'SHA256SUMS')
        (HERE/'evidence/final-packages.json').write_text(json.dumps(checks,indent=2)+'\n')
        existed=TEMP.exists()
        prior_cleanup=HERE/'evidence/cleanup.json'
        temporary_files=[f for f in TEMP.rglob('*') if f.is_file()] if existed else []
        removed_files=len(temporary_files);removed_bytes=sum(f.stat().st_size for f in temporary_files)
        if TEMP.exists():shutil.rmtree(TEMP)
        assert not TEMP.exists()
        cleanup=dict(temporary=str(TEMP),deleted=True,removed_files=removed_files,removed_logical_bytes=removed_bytes,
            residual_test_processes=active(),protected_input_changes=0,
            volume_uuid=volume['VolumeUUID'],filesystem=volume['FilesystemType'],writable=True,
            retained_media='research/v310_body/fix/evidence/media-retention.json',
            finished_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
        if not existed and prior_cleanup.exists():
            cleanup=json.loads(prior_cleanup.read_text())
            assert cleanup['deleted'] and cleanup['temporary']==str(TEMP)
        assert not cleanup['residual_test_processes']
        (HERE/'evidence/cleanup.json').write_text(json.dumps(cleanup,indent=2)+'\n')
        report=HERE.parent/'REPORT.md';source=report.read_text()
        marker='清理状态：待最终封存。'
        if marker in source:
            report.write_text(source.replace(marker,
                '清理状态：指定 TMP 已删除，本任务残留测试进程 0；'+str(len(frozen))+' 个冻结文件逐项 SHA-256 核对，变化 0。清理完成于 '+cleanup['finished_utc']+'，详见 [cleanup.json](fix/evidence/cleanup.json)。'))
        else:assert '清理状态：指定 TMP 已删除' in source
        for progress in (HERE/'PROGRESS.md',HERE.parent/'PROGRESS.md'):
            line='最终封存：TMP 已删除，残留测试 0，冻结输入变化 0；清理收据 fix/evidence/cleanup.json。'
            if line not in progress.read_text():progress.write_text(progress.read_text()+'\n'+line+'\n')
        check_language()
    paths=[]
    target=HERE.parent/('SHA256SUMS' if a.final else 'SHA256SUMS.partial')
    for base in (HERE.parent,ROOT/'firmware/image_v310',ROOT/'firmware/engine_v66_g155b',
                 ROOT/'firmware/package_v310_g155b',ROOT/'firmware/package_v310_g155b_test'):
        paths.extend(f for f in base.rglob('*') if f.is_file() and f not in (HERE.parent/'SHA256SUMS',HERE.parent/'SHA256SUMS.partial'))
    count=sums(paths,target)
    for line in target.read_text().splitlines():
        digest,name=line.split('  ',1)
        assert sha(ROOT/name)==digest,name
    print(json.dumps(dict(final=a.final,files=count,target=str(target.relative_to(ROOT)),sha256=sha(target),all_hashes_verified=True)))


if __name__=='__main__':main()
