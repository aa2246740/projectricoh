"""把已验证的 g154 驱动复制到本轮，按实际 Looks 数展开测试。"""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import *
import difflib


def change(text, old, new):
    assert text.count(old) == 1, (old, text.count(old))
    return text.replace(old, new)


def main():
    guard()
    base = ROOT / 'research/g154'
    diff = []
    native = (base / 'native_support.py').read_text().replace('g154-impl-r1', 'g154-looks-r1')
    native = native.replace('firmware/package_v39_g154_test/local/SD_ROOT', 'firmware/package_v39_g154_looks18_test/local/SD_ROOT')
    native = native.replace('firmware/engine_v63_g154/candidate/local/full-r13/engine.elf',
                            'firmware/package_v39_g154_looks18_test/local/build/engine.elf')
    native = change(native, 'self.goto(17+number)',
                    "raw=H.DAT_BYTES[self.dat_path]\n"
                    "            shared=int.from_bytes(raw[192:196],'big')\n"
                    "            area=shared+int.from_bytes(raw[shared+64:shared+68],'big')\n"
                    "            count=int.from_bytes(raw[area+10:area+12],'big')\n"
                    "            self.goto(7+count+number)")
    reference = (base / 'reference.py').read_text().replace('g154-impl-r1', 'g154-looks-r1')
    verify = (base / 'verify.py').read_text()
    verify = change(verify, 'from reference import Reference,user_record',
                    'from reference import Reference,user_record\nLOOKS=18\nUSER_START=8+LOOKS\nHINT=USER_START+3')
    verify = change(verify, 'elif row<18:', 'elif row<USER_START:')
    verify = change(verify, 'elif row<21:', 'elif row<HINT:')
    verify = change(verify, 'user_record(raw,row-17)', 'user_record(raw,row-USER_START+1)')
    verify = change(verify, "assert cam.ui('count')==22", "assert cam.ui('count')==HINT+1")
    verify = change(verify, "targets=list(range(22))+list(range(20,-1,-1)) if unit!='28mm' else [3,7,8,17,18,20,21,0]",
                    'targets=list(range(HINT+1))+list(range(HINT-1,-1,-1))')
    verify = change(verify, 'if 8<=row<18:', 'if 8<=row<USER_START:')
    verify = change(verify, 'if 18<=row<21:', 'if USER_START<=row<HINT:')
    verify = change(verify, 'user_record(H.DAT_BYTES[cam.dat_path],row-17)',
                    'user_record(H.DAT_BYTES[cam.dat_path],row-USER_START+1)')
    verify = change(verify, 'if row==21:', 'if row==HINT:')
    verify = verify.replace('cam.goto(21)', 'cam.goto(HINT)').replace("['cur']==21", "['cur']==HINT")
    verify = change(verify, 'for row in (2,8,18):', 'for row in (2,*range(8,USER_START),USER_START):')
    verify = change(verify, "reopened['cur']==20", "reopened['cur']==HINT-1")
    verify = change(verify, 'wanted(cam,20,ref)', 'wanted(cam,HINT-1,ref)')
    verify = change(verify, 'old=Reference(153);new=Reference(154)', 'old=Reference(154);new=old')
    verify = change(verify, 'firmware/package_v39_g153_test/local/SD_ROOT/GXRCE.DAT',
                    'firmware/package_v39_g154_test/local/SD_ROOT/GXRCE.DAT')
    verify = change(verify, "directory=HERE/'evidence/outputs'", "directory=H.PACKAGE.parent/'evidence/outputs'")
    verify = change(verify, 'directory.mkdir(exist_ok=True)', 'directory.mkdir(parents=True,exist_ok=True)')
    verify = change(verify, "assert equal or (unit==2 and kind=='user' and bbase[0]!=4)", 'assert equal')
    verify = verify.replace("name+'-g153.bin'", "name+'-baseline154.bin'").replace("name+'-g154.bin'", "name+'-looks18.bin'")
    run = (base / 'run.py').read_text().replace('g154-impl-r1', 'g154-looks-r1')
    run = change(run, "dat_sha256={s:hashlib.sha256((ROOT/('firmware/package_v39_g154'+s+'/local/SD_ROOT/GXRCE.DAT')).read_bytes()).hexdigest() for s in ('','_test')}",
        "dat_sha256={s:hashlib.sha256((ROOT/('firmware/'+s+'/local/SD_ROOT/GXRCE.DAT')).read_bytes()).hexdigest() for s in ('package_v39_g154_test','package_v39_g154_looks18_test')}")
    identity = (base / 'identity_checks.py').read_text()
    identity = change(identity, "new=root/'firmware/package_v39_g154/local/SD_ROOT/GXRCE.DAT'",
                      "new=root/'firmware/package_v39_g154_looks18_test/local/build/release-zero-users.DAT'")
    identity = change(identity, "H.ENGINE=root/('firmware/'+engine+'/candidate/local/full-r13/engine.elf')",
                      "H.ENGINE=(root/'firmware/package_v39_g154_looks18_test/local/build/engine.elf') if model_generation==154 else root/('firmware/'+engine+'/candidate/local/full-r13/engine.elf')")
    identity = change(identity, "(22 if name=='g154-test' else 19)", "(30 if name=='g154-test' else 27)")
    capacity = (base / 'cap_checks.py').read_text()
    capacity = change(capacity, 'def fixture(users,looks=10):', 'def fixture(users,looks=18):')
    capacity = change(capacity, 'if looks!=10:', 'if looks!=18:')
    capacity = capacity.replace('firmware/engine_v63_g154/candidate/user_entries.py',
                                'firmware/engine_v65_g154_looks/candidate/user_entries.py')
    capacity = change(capacity, '(1,8,9,19,22,49)', '(1,8,9,27,30,49)')
    capacity = change(capacity, '((30,10),(31,10),(32,10),(32,8),(32,0),(0,0))',
                      '((22,18),(23,18),(32,18),(32,8),(32,0),(0,0))')
    scripts = (('native_support.py', native), ('reference.py', reference), ('verify.py', verify),
               ('run.py', run), ('identity_checks.py', identity), ('cap_checks.py', capacity))
    for name, source in scripts:
        (HERE / name).write_text(source)
        diff.extend(difflib.unified_diff((base / name).read_text().splitlines(True), source.splitlines(True),
                    fromfile=str((base / name).relative_to(ROOT)), tofile=str((HERE / name).relative_to(ROOT))))
    (HERE / 'evidence/check-retarget.diff').write_text(''.join(diff))
    print(json.dumps(dict(status='PASS', scripts=len(scripts), looks=18, units=3)))


if __name__ == '__main__':
    main()
