"""Audit the delivered candidate, protected inputs, source diff and SHA256SUMS."""
from pathlib import Path
import difflib
import hashlib
import json
import sys
import zlib
sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as c


def main():
    c.guard()
    before=json.loads((c.LOCAL/'scope-before.json').read_text())
    changed=[name for name,digest in before['files'].items()
             if not (c.ROOT/name).is_file() or c.sha(c.ROOT/name)!=digest]
    assert not changed, changed
    git=c.run(['git','status','--porcelain=v1','--untracked-files=no'],'git-after').stdout
    assert git==before['git'], 'Shared tracked status changed; inspect without reverting it'
    c.save(c.LOCAL/'scope.json',dict(status='PASS',protected_files=len(before['files']),
        changed_inputs=changed,tracked_git_status_unchanged=True,write_scope=str(c.HERE),
        resident_rebuilt=False,camera_access=False,card_access=False,commit=False,push=False))
    previous=c.ROOT/'firmware/engine_fix_r1'
    patches=[];changes=[]
    for relative in ('engine_services','containers/product'):
        for path in sorted((c.HERE/relative).rglob('*')):
            if not path.is_file():continue
            old=previous/path.relative_to(c.HERE)
            a=old.read_text().splitlines(True) if old.exists() else []
            b=path.read_text().splitlines(True)
            if a!=b:
                changes.append(str(path.relative_to(c.HERE)))
                patches.extend(difflib.unified_diff(a,b,fromfile=str(old.relative_to(c.ROOT)),
                    tofile=str(path.relative_to(c.ROOT))))
    (c.LOCAL/'source-diff.patch').write_text(''.join(patches))
    c.save(c.LOCAL/'source-changes.json',changes)
    folder=c.LOCAL/'product/candidates/full-r3'
    metadata=json.loads((folder/'layout.json').read_text())
    blob=(folder/'GXRCE.DAT').read_bytes()
    assert int.from_bytes(blob[28:32],'big')==105
    header=bytearray(blob[:256]);header[20:24]=bytes(4)
    assert int.from_bytes(blob[20:24],'big')==zlib.crc32(header)&0xffffffff
    assert int.from_bytes(blob[24:28],'big')==zlib.crc32(blob[256:])&0xffffffff
    for group in ('sources','tools'):
        assert all(c.sha(c.ROOT/name)==digest for name,digest in metadata[group].items())
    reader=c.load(c.ROOT/'firmware/stage2l_switch/tools/build.py','final_elf_reader')
    engine=reader.Elf(folder/'engine.elf');section=next(s for s in engine.sections if s['name']=='.engine')
    assert engine.content(section)==blob[section['va']:section['va']+section['size']]==(folder/'engine.bin').read_bytes()
    assert metadata['engine_sha256']==hashlib.sha256(engine.content(section)).hexdigest()
    assert metadata['bss_bytes']==next(s['size'] for s in engine.sections if s['name']=='.bss')
    previous_layout=json.loads((previous/'local/product/candidates/full-r2/layout.json').read_text())
    assert metadata['flags']==previous_layout['flags'] and metadata['lto']==previous_layout['lto']
    assert metadata['tools']==previous_layout['tools']
    checks=json.loads((c.LOCAL/'test-summary.json').read_text())
    assert checks['status']=='PASS' and checks['total_cases']==258 and checks['remaining_risk_cases']==3
    assert not checks['F02_unconditional_preservation_proven']
    artifact=json.loads((c.LOCAL/'artifact-inspection.json').read_text())
    assert artifact['status']=='PASS' and artifact['artifacts']['full_r3']['sha256']==c.sha(folder/'GXRCE.DAT')
    for unit in range(3):
        log=(c.LOCAL/'logs'/f'extra-firstboot-empty-{unit}.log').read_text()
        assert f'main_request={artifact["artifacts"]["full_r3"]["main_request"]}' in log
        assert 'IROM_reboot=OK' in log and 'session_workspace=1' in log
    for row in json.loads((c.LOCAL/'revision-acceptance.json').read_text()):
        assert row['status']=='PASS' and row['container_sha256']==c.sha(folder/'GXRCE.DAT')
    report=c.HERE/'REPORT.md'
    assert report.is_file() and c.sha(folder/'GXRCE.DAT') in report.read_text()
    c.save(c.LOCAL/'acceptance-summary.json',dict(status='PASS_WITH_DOCUMENTED_LIMITATION',
        container=str((folder/'GXRCE.DAT').relative_to(c.HERE)),sha256=c.sha(folder/'GXRCE.DAT'),
        generation=105,checks=checks,engine_equals_ELF=True,source_hashes_verified=len(metadata['sources']),
        tool_hashes_verified=len(metadata['tools']),compiler_flags_unchanged=True,
        F01='closed in host evidence',F02='requested fallback; persistent -1 remains ambiguous',
        source_diff_files=len(changes),scope_unchanged=True,camera_acceptance=False))
    sums=c.HERE/'SHA256SUMS'
    paths=sorted(p for p in c.HERE.rglob('*') if p.is_file() and p!=sums)
    assert not any(p.is_symlink() for p in c.HERE.rglob('*'))
    sums.write_text(''.join(f'{c.sha(p)}  {p.relative_to(c.HERE)}\n' for p in paths))
    for line in sums.read_text().splitlines():
        digest,name=line.split('  ',1);assert c.sha(c.HERE/name)==digest
    print(f'PASS {len(before["files"])} protected inputs unchanged; {checks["total_cases"]} checks; '
          f'3 residual-risk reproductions kept separate; SHA256SUMS verified {len(paths)} files')


if __name__=='__main__':
    main()
