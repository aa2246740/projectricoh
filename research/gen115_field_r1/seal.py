"""Verify frozen inputs and hash all task artifacts. Does not rebuild inputs."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import boundary as b
import json
import re

def files():
    return sorted(p for p in b.HERE.rglob('*') if p.is_file() and p.name not in ('SHA256SUMS','decisions.tsv'))

def main():
    b.verify()
    report=b.HERE/'REPORT.md';raw=report.read_bytes();assert b'\0' not in raw
    text=raw.decode();assert text.startswith('01/02 没有以完整配方进入')
    for p in b.HERE.glob('*.py'):compile(p.read_text(),str(p),'exec')
    links=[]
    for target in re.findall(r'\]\(([^)]+)\)',text):
        if '://' in target:continue
        path=(b.HERE/target.split('#',1)[0]).resolve()
        assert path.is_file() or path==b.HERE/'SHA256SUMS', 'broken report link: '+target
        links.append(target)
    accepted=json.loads((b.LOCAL/'acceptance.json').read_text())
    assert accepted['final_source_and_machine_identity'] and accepted['old04_controls_reproduced']
    assert accepted['JPEG_DNG_image_setting_fields_equal']
    assert all(not p.is_symlink() for p in files()),'task outputs must be real files'
    frozen=json.loads((b.LOCAL/'frozen_inputs.json').read_text())
    assert not any(Path(p).name=='decisions.tsv' or p.startswith(('tools/native_harness/','tools/gxr_emulator/')) for p in frozen)
    count=len(files())+(not (b.LOCAL/'seal_summary.json').exists())
    b.dump('seal_summary.json',dict(protected_inputs=len(frozen),unchanged=True,artifact_files=count,
        report_sha256=b.sha(report),relative_links_verified=len(links),no_NUL=True,
        scope='host-only diagnosis/design; no firmware build, card/camera/device/network access',
        applied='no full recipe01/02 in the two field JPEGs; historical transient writes unknown',
        unresolved=['exact H07/T/RPC blocker','28mm actual load/init rejection'],
        checksums='SHA256SUMS covers report, scripts and all local evidence; excludes itself'))
    paths=files();assert len(paths)==count
    manifest=b.HERE/'SHA256SUMS'
    manifest.write_text(''.join(b.sha(p)+'  '+str(p.relative_to(b.HERE))+'\n' for p in paths))
    for target in links:
        assert (b.HERE/target.split('#',1)[0]).resolve().is_file(),target
    for line in manifest.read_text().splitlines():
        digest,name=line.split('  ',1);assert b.sha(b.HERE/name)==digest,name
    print(json.dumps(dict(status='SEALED',protected_inputs=len(frozen),artifact_files=len(paths),
        report_bytes=len(raw),report_sha256=b.sha(report),checksums_verified=True),ensure_ascii=False))

if __name__=='__main__':main()
