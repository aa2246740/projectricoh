"""Independent preservation, diff and reviewed-service comparisons."""
from pathlib import Path
import difflib
import importlib.util
import json

HERE=Path(__file__).resolve().parent
sp=importlib.util.spec_from_file_location('driver',HERE/'run_review.py')
r=importlib.util.module_from_spec(sp);sp.loader.exec_module(r)

def main():
    r.freeze();c=r.c;prior=r.SOURCE/'local/staged_r2'
    preserved=json.loads((prior/'preserved.json').read_text())
    for name,sha in preserved.items():assert c.sha(prior/name)==sha,name
    changed=[];unchanged=[];patch=[];old_names=set()
    for p in sorted((prior/'source').iterdir()):
        assert p.is_file();old_names.add(p.name);new=r.SOURCE/p.name
        if p.read_bytes()==new.read_bytes():unchanged.append(p.name)
        else:
            changed.append(p.name)
            patch.extend(difflib.unified_diff(p.read_text().splitlines(True),new.read_text().splitlines(True),fromfile='r2/'+p.name,tofile='r3/'+p.name))
    added=sorted(p.name for p in r.SOURCE.iterdir() if p.is_file() and p.name not in old_names)
    allowed={'REPORT.md','USER_GUIDE.md','audit.py','build.py','decode.py','freeze.py','host_checks.c','probe.c','probe.h','stage.py','verify.py'}
    assert set(changed)<=allowed,changed
    assert set(added)=={'r3_checks.c','r3_replay.py','r3_verify.py','write_trace.c'},added
    (HERE/'r2-to-r3.patch').write_text(''.join(patch))
    for obj in ('1-timing.o','2-kernel.o'):
        assert (prior/'evidence/build'/obj).read_bytes()==(r.SOURCE/'local/build'/obj).read_bytes(),obj
        assert (c.LOCAL/'build'/obj).read_bytes()==(r.SOURCE/'local/build'/obj).read_bytes(),obj
    reviewed=r.ROOT/'research/review_publish_v114/rebuild'
    sections={}
    for obj in sorted((c.ARCHIVE.parent).glob('*.o')):
        a,b=c.Elf(obj),c.Elf(reviewed/obj.name)
        aa={s['name']:a.content(s) for s in a.sections if s['flags']&2 or s['type']==4}
        bb={s['name']:b.content(s) for s in b.sections if s['flags']&2 or s['type']==4}
        assert aa==bb,('reviewed gen114 target section mismatch',obj.name)
        candidate=c.Elf(r.SOURCE/'local/services114/build'/obj.name)
        cc={s['name']:candidate.content(s) for s in candidate.sections if s['flags']&2 or s['type']==4}
        assert cc==bb,('staged gen114 target section mismatch',obj.name)
        sections[obj.name]={name:len(value) for name,value in aa.items()}
    assert len(sections)==8
    source_checks={}
    for p in sorted((r.SOURCE/'local/services114/candidate/engine_services').iterdir()):
        if p.is_file():
            origin=c.GEN114/'candidate/engine_services'/p.name
            assert p.read_bytes()==origin.read_bytes(),p
            source_checks[p.name]=c.sha(p)
    for name in ('resident.h','abi.h','gxrce.h','shared.c'):
        assert (r.SOURCE/'local/services114/resident'/name).read_bytes()==(c.R/name).read_bytes()
    # Build the real-generation negative check with sanitizer-enabled resident/services.
    cmds={x['label']:x['argv'] for x in map(json.loads,(r.OUT/'commands.jsonl').read_text().splitlines())}
    cmd=list(cmds['host-compile-0']);cmd[cmd.index('-c')+1]=str(HERE/'install_real.c')
    obj=HERE/'install_real.o';cmd[cmd.index('-o')+1]=str(obj);r.run(cmd,'real-install-compile')
    link=[str(obj) if x.endswith('/0-host_checks.o') else x for x in cmds['host-link']]
    binary=HERE/'install_real';link[link.index('-o')+1]=str(binary);r.run(link,'real-install-link')
    fixture115=r.ROOT/'firmware/engine_v36_r28/local/staged/SD_ROOT/GXRCE.DAT'
    result=r.run([binary,r.OUT/'GXRCE.DAT',c.FULL,c.FULL114,fixture115],'real-install-run')
    print(result.stdout,end='')
    r.save(HERE/'independent-audit.json',dict(status='PASS',dat_sha256=c.sha(r.SOURCE/'local/staged/GXRCE.DAT'),
        r2_preserved_files=len(preserved),changed=changed,unchanged=unchanged,added=added,
        unchanged_objects=['1-timing.o','2-kernel.o'],reviewed_gen114_sections=sections,
        reviewed_service_sources=source_checks,
        archive_whole_byte_equal=(c.ARCHIVE.read_bytes()==(reviewed/'libgxr_services.a').read_bytes()),
        archive_note='Only allocated and relocation sections claim byte equality; LTO path metadata differs.',
        fixture115=dict(path=str(fixture115.relative_to(r.ROOT)),sha256=c.sha(fixture115),bytes=fixture115.stat().st_size),
        real_generations=[113,114,115],install=result.stdout.strip()))
    print('PASS r2 diff confined; original timing/kernel objects unchanged; 8 reviewed gen114 target objects byte-equal')
    r.freeze()

if __name__=='__main__':main()
