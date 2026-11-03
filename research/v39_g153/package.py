"""Assemble the two g153 packages and verify full image and data identities."""
from pathlib import Path
import hashlib
import importlib.util
import json
import shutil
import sys

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
BUILT = ROOT / 'firmware/engine_v62_g153/candidate/local/full-r13'
RESIDENT = HERE / 'local/body/local/resident'


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    sys.path.insert(0, str(HERE))
    from dat_format import seal, sections, strict_effects, expand_effect, expand, u16, u32
    image = load(ROOT / 'research/body_v39/build_image.py', 'g153_image_method')
    image.WORK = HERE
    zip_sha, official = image.official_files()
    v38_manifest = json.loads((image.V38 / 'patch-manifest.json').read_text())
    v38, _ = image.image(official['ilaunch3'], v38_manifest, image.V38 / 'build/resident.elf')
    assert sha(v38) == image.V38_SHA
    manifest = json.loads((RESIDENT / 'patch-manifest.json').read_text())
    body, raw_resident = image.image(official['ilaunch3'], manifest, RESIDENT / 'build/resident.elf')
    (HERE / 'local/ilaunch3').write_bytes(body)
    sys.path.insert(0, str(ROOT / 'research/review_body_v39/checks'))
    comparison = load(ROOT / 'research/review_body_v39/checks/identity_compare.py', 'g153_identity_compare')
    identity = comparison.compare(ROOT / 'firmware/resident_v39/local/resident/build/resident.elf',
                                  RESIDENT / 'build/resident.elf',
                                  ROOT / 'firmware/package_v39_g151/local/SD_ROOT/ilaunch3',
                                  HERE / 'local/ilaunch3')
    assert identity['build_id_changed'] and not identity['abi_id_changed']
    (HERE / 'evidence/identity-compare.json').write_text(json.dumps(identity, indent=2) + '\n')
    assert manifest == json.loads((ROOT / 'firmware/resident_v39/local/resident/patch-manifest.json').read_text())
    release = (BUILT / 'GXRCE.DAT').read_bytes()
    sections(release)
    fx = strict_effects(release)
    assert u32(release, 28) == 153 and fx['count'] == 10
    old_release = (ROOT / 'firmware/package_v38_g152/local/SD_ROOT/GXRCE.DAT').read_bytes()
    old_test = (ROOT / 'firmware/package_v38_g152_test/local/SD_ROOT/GXRCE.DAT').read_bytes()
    for i in range(10):
        assert expand_effect(release, i) == expand_effect(old_release, i)
    for unit in range(3):
        for slot in range(1, 9):
            assert expand(release, unit, slot) == expand(old_release, unit, slot)
    old_knobs, new_knobs = u32(old_release, 204) + 3392, u32(release, 204) + 3392
    assert old_release[old_knobs:old_knobs+7904] == release[new_knobs:new_knobs+7904]
    start, source = u32(release, 204) + 1408, u32(old_test, 204) + 1408
    test = bytearray(release)
    test[start:start+1984] = old_test[source:source+1984]
    test = seal(test)
    assert u16(release, start+24) == 0 and u16(test, start+24) == 3
    assert test[start:start+1984] == old_test[source:source+1984]
    trust = json.loads((RESIDENT / 'trust.json').read_text())
    assert release[80:112].hex() == trust['resident_build_id']
    assert release[212:228].hex() == trust['resident_abi_id']
    results = {}
    old_package = ROOT / 'firmware/package_v38_g152'
    old_manifest = json.loads((old_package / 'MANIFEST.json').read_text())
    for name, dat, users in (('package_v39_g153', release, 0), ('package_v39_g153_test', test, 3)):
        target = ROOT / 'firmware' / name
        output = target / 'local/SD_ROOT'
        output.mkdir(parents=True, exist_ok=True)
        for filename, data in official.items():
            (output / filename).write_bytes(body if filename == 'ilaunch3' else data)
        (output / 'GXRCE.DAT').write_bytes(dat)
        assert len(list(output.iterdir())) == 30
        assert all((output / filename).read_bytes() == data for filename, data in official.items() if filename != 'ilaunch3')
        link = target / 'SD_ROOT'
        if not link.is_symlink():
            link.symlink_to('local/SD_ROOT')
        (target / '.gitignore').write_text('local/\nSD_ROOT\n')
        disable = target / 'local/disable'
        disable.mkdir(exist_ok=True)
        shutil.copyfile(ROOT / 'firmware/package_v39_g151/local/disable/GXRCE.CTL', disable / 'GXRCE.CTL')
        package_manifest = dict(old_manifest, generation=153, dat_sha256=sha(dat), dat_bytes=len(dat), users=users,
                                effects=strict_effects(dat), body_sha256=sha(body), official_companion_count=28,
                                resident_build_id=trust['resident_build_id'], resident_abi_id=trust['resident_abi_id'])
        package_manifest.pop('unchanged_body_files', None)
        (target / 'MANIFEST.json').write_text(json.dumps(package_manifest, ensure_ascii=False, indent=2) + '\n')
        for filename in ('LICENSE-CC-BY-SA-4.0.txt', 'FILM-PROFILES-NOTICE.txt', 'FOTUFILM-NOTICE.txt'):
            shutil.copyfile(old_package / filename, target / filename)
        files = sorted(p for p in target.rglob('*') if p.is_file() and not p.is_symlink() and p.name not in ('.gitignore', 'SHA256SUMS'))
        (target / 'SHA256SUMS').write_text(''.join(f'{sha(p.read_bytes())}  {p.relative_to(ROOT)}\n' for p in files))
        results[name] = dict(dat_sha256=sha(dat), body_sha256=sha(body), users=users, effects=10,
                             official_companions=28, files_in_SD_ROOT=30)
    receipt = dict(status='PASS', official_zip_sha256=zip_sha, method_check_v38=sha(v38),
                   body_sha256=sha(body), resident_sha256=sha(raw_resident), packages=results,
                   effects_552_bytes_equal_g152=10, builtin_552_bytes_equal_g152=24,
                   R3_bytes_equal_g152=7904, user_extension_bytes_equal_g152=1984,
                   identity=identity, trust=trust)
    (HERE / 'evidence/package.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(dict(status='PASS', body_sha256=sha(body), packages=results)))


if __name__ == '__main__':
    main()
