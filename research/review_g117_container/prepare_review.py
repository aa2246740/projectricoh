"""Prepare isolated copies; product and official inputs remain read-only."""
from pathlib import Path
import difflib
import hashlib
import json
import shutil

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
ORIGINAL = ROOT / 'firmware/engine_v38_ro'
TREE = OUT / 'isolated'
CAND = TREE / 'candidate'


def main():
    assert not CAND.exists()
    for name in ('candidate', 'resident'):
        shutil.copytree(ORIGINAL / name, TREE / name,
                        ignore=shutil.ignore_patterns('local', '__pycache__'))
    local = CAND / 'local'
    local.mkdir()
    for name in ('native_seed_model.h', 'native_enum.h', 'native_get_mode.h'):
        shutil.copyfile(ORIGINAL / 'candidate/local' / name, local / name)
    common = CAND / 'common.py'
    text = common.read_text().replace('ROOT = HERE.parents[2]', 'ROOT = Path(' + repr(str(ROOT)) + ')')
    start = text.index('def guard():')
    end = text.index('\ndef freeze_check():', start)
    text = text[:start] + '''def guard():
    assert HERE == Path(''' + repr(str(CAND)) + ''')
    LOCAL.resolve().relative_to(Path(''' + repr(str(OUT)) + '''))
    (LOCAL / 'tmp').mkdir(parents=True, exist_ok=True)

''' + text[end:]
    common.write_text(text)
    service = CAND / 'service_build.py'
    text = service.read_text()
    original_seed = "'-frandom-seed='+str(src.relative_to(c.ROOT))"
    routed_seed = original_seed + ".replace('research/review_g117_container/isolated/', 'firmware/engine_v38_ro/')"
    assert original_seed in text
    service.write_text(text.replace(original_seed, routed_seed))
    host = CAND / 'host_v34c.c'
    text = host.read_text()
    text = text.replace('../../engine_v37/baseline/engine_services/native_seed.c',
                        str(ROOT / 'firmware/engine_v37/baseline/engine_services/native_seed.c'))
    host.write_text(text)
    changes = []
    for p in sorted(TREE.rglob('*')):
        if not p.is_file() or 'local' in p.relative_to(TREE).parts:
            continue
        original = ORIGINAL / p.relative_to(TREE)
        if original.is_file() and p.read_bytes() != original.read_bytes():
            changes.extend(difflib.unified_diff(original.read_text().splitlines(True), p.read_text().splitlines(True),
                           fromfile=str(original.relative_to(ROOT)), tofile=str(p.relative_to(OUT))))
    (OUT / 'routing.patch').write_text(''.join(changes))
    native = OUT / 'native_harness'
    shutil.copytree(ROOT / 'tools/native_harness', native,
                    ignore=shutil.ignore_patterns('local', '__pycache__'))
    (native / 'local').mkdir()
    shutil.copyfile(ROOT / 'tools/native_harness/local/protected-inputs.json', native / 'local/protected-inputs.json')
    for name, old in (('guard.py', 'ROOT = HERE.parents[1]'),
                      ('image_loader.py', 'ROOT = Path(__file__).resolve().parents[2]')):
        p = native / name
        text = p.read_text()
        assert old in text, (name, old)
        p.write_text(text.replace(old, 'ROOT = Path(' + repr(str(ROOT)) + ')'))
    p = OUT / 'run_v35_g117.py'
    text = (ORIGINAL / p.name).read_text()
    text = text.replace('ROOT = Path(__file__).resolve().parents[2]', 'ROOT = Path(' + repr(str(ROOT)) + ')')
    text = text.replace('ROOT / "firmware/engine_v38_ro/candidate/local/full-r13/GXRCE.DAT"',
                        'Path(' + repr(str(CAND / 'local/full-r13/GXRCE.DAT')) + ')')
    text = text.replace('ROOT / "firmware/engine_v38_ro/candidate/local/full-r13/engine.elf"',
                        'Path(' + repr(str(CAND / 'local/full-r13/engine.elf')) + ')')
    p.write_text(text)
    for name in ('run_host117.py',):
        p = OUT / name
        text = (ORIGINAL / name).read_text()
        text = text.replace('ROOT=HERE.parents[1]', 'ROOT=Path(' + repr(str(ROOT)) + ')')
        text = text.replace("C=HERE/'candidate';OUT=HERE/'local'", "C=HERE/'isolated/candidate';OUT=HERE/'runs'")
        p.write_text(text)
    (OUT / 'runs').mkdir(exist_ok=True)
    (OUT / 'copied-inputs.json').write_text(json.dumps({str(p.relative_to(OUT)): hashlib.sha256(p.read_bytes()).hexdigest()
        for base in (TREE, native) for p in sorted(base.rglob('*')) if p.is_file()}, indent=2) + '\n')
    print('PASS isolated source and native harness copies')


if __name__ == '__main__':
    main()
