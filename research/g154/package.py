"""从 g153 包复制 29 个升级文件，只替换 g154 DAT。"""
from pathlib import Path
import hashlib
import json
import shutil
import sys

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'research/v39_g153'))
from dat_format import seal,sections,strict_effects,expand,expand_effect,u32,u16


def sha(data):return hashlib.sha256(data).hexdigest()


def main():
    source=ROOT/'firmware/package_v39_g153'
    release=(ROOT/'firmware/engine_v63_g154/candidate/local/full-r13/GXRCE.DAT').read_bytes()
    previous=(source/'local/SD_ROOT/GXRCE.DAT').read_bytes()
    previous_test=(ROOT/'firmware/package_v39_g153_test/local/SD_ROOT/GXRCE.DAT').read_bytes()
    sections(release);effects=strict_effects(release)
    assert u32(release,28)==154 and effects['count']==10
    assert all(expand(release,u,s)==expand(previous,u,s) for u in range(3) for s in range(1,9))
    assert all(expand_effect(release,i)==expand_effect(previous,i) for i in range(10))
    start,old=u32(release,204)+1408,u32(previous_test,204)+1408
    test=bytearray(release);test[start:start+1984]=previous_test[old:old+1984];test=seal(test)
    assert u16(release,start+24)==0 and u16(test,start+24)==3
    assert test[start:start+1984]==previous_test[old:old+1984]
    assert release[u32(release,204)+3392:]==previous[u32(previous,204)+3392:]
    body=(source/'local/SD_ROOT/ilaunch3').read_bytes()
    assert sha(body)=='8233a1c464b29ba88cfdfce1d083b9bf652586edeb216cacf6f16cf36788b25d'
    results={}
    for suffix,dat,users in (('',release,0),('_test',test,3)):
        target=ROOT/('firmware/package_v39_g154'+suffix)
        output=target/'local/SD_ROOT';output.mkdir(parents=True,exist_ok=True)
        original_files=[p for p in (source/'local/SD_ROOT').iterdir() if p.name!='GXRCE.DAT']
        assert len(original_files)==29
        for p in original_files:shutil.copyfile(p,output/p.name)
        (output/'GXRCE.DAT').write_bytes(dat)
        assert all((output/p.name).read_bytes()==p.read_bytes() for p in original_files)
        assert len(list(output.iterdir()))==30
        for name in ('LICENSE-CC-BY-SA-4.0.txt','FILM-PROFILES-NOTICE.txt','FOTUFILM-NOTICE.txt'):
            shutil.copyfile(source/name,target/name)
        (target/'local/disable').mkdir(exist_ok=True)
        shutil.copyfile(source/'local/disable/GXRCE.CTL',target/'local/disable/GXRCE.CTL')
        if not (target/'SD_ROOT').is_symlink():(target/'SD_ROOT').symlink_to('local/SD_ROOT')
        (target/'.gitignore').write_text('local/\nSD_ROOT\n')
        manifest=json.loads((source/'MANIFEST.json').read_text())
        manifest.update(generation=154,dat_sha256=sha(dat),dat_bytes=len(dat),users=users,effects=effects,
            body_sha256=sha(body),user_entry_limit=30,logical_rows=19+users,
            upgrade_files_identical_to='package_v39_g153')
        (target/'MANIFEST.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
        files=sorted(p for p in target.rglob('*') if p.is_file() and not p.is_symlink() and p.name not in ('.gitignore','SHA256SUMS'))
        (target/'SHA256SUMS').write_text(''.join(f'{sha(p.read_bytes())}  {p.relative_to(ROOT)}\n' for p in files))
        results[target.name]=dict(dat_sha256=sha(dat),dat_bytes=len(dat),users=users,upgrade_files_equal=29)
    receipt=dict(status='PASS',body_sha256=sha(body),builtin_552_equal=24,look_552_equal=30,
        R3_bytes_equal=7904,test_user_extension_equal=1984,packages=results)
    (HERE/'evidence/package.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps(receipt))


if __name__=='__main__':main()
