"""复制 g154 源码；只调整构建入口和 GXFX 数据容量。"""
import difflib
import shutil
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import *


def main():
    guard()
    if not ENGINE.exists():
        shutil.copytree(BASE_ENGINE, ENGINE,
                        ignore=shutil.ignore_patterns('local', '__pycache__', '.DS_Store'))
    effects = selected()
    raw = (BASE_PACKAGE / 'local/SD_ROOT/GXRCE.DAT').read_bytes()
    builtin = buckets(raw)
    caps, fx_bytes = pool_layout(effects, builtin)
    assert len(effects) == 18 and caps == (0, 18, 16, 18)
    save(DATA / 'local/effects.json', effects)
    product = ENGINE / 'candidate/containers/product'
    source = (BASE_ENGINE / 'candidate/containers/product/looks_data.py').read_text()
    for old, new in (("WORK=ROOT/'research/looks_g152'", "WORK=ROOT/'artifacts/downloads/g154-looks-r1'"),
                     ('CAPACITY=10', 'CAPACITY=18'), ('CAPS=(8,28,32,32)', 'CAPS=(0,18,16,18)')):
        assert source.count(old) == 1
        source = source.replace(old, new)
    (product / 'looks_data.py').write_text(source)
    (ENGINE / 'candidate/build154.py').write_text(
        "from pathlib import Path\nimport runpy\n"
        "runpy.run_path(str(Path(__file__).resolve().parents[3] / 'research/g154_looks_r1/build.py'), run_name='__main__')\n")
    changes, diff = [], []
    for path in sorted(ENGINE.rglob('*')):
        if not path.is_file() or 'local' in path.relative_to(ENGINE).parts:
            continue
        relative = path.relative_to(ENGINE)
        previous = BASE_ENGINE / relative
        if not previous.is_file() or previous.read_bytes() != path.read_bytes():
            changes.append(str(relative))
            diff.extend(difflib.unified_diff(previous.read_text().splitlines(True), path.read_text().splitlines(True),
                fromfile=str(previous.relative_to(ROOT)), tofile=str(path.relative_to(ROOT))))
    assert changes == ['candidate/build154.py', 'candidate/containers/product/looks_data.py'], changes
    (HERE / 'evidence/source.diff').write_text(''.join(diff))
    save(HERE / 'evidence/source-changes.json', dict(status='PASS', files=changes,
         C_sources_unchanged=True, resident_unchanged=True, engine_services_unchanged=True))
    original_fx_bytes = effect_area(raw)[1]
    steps = []
    for count in range(10, 19):
        cap, size = pool_layout(effects[:count], builtin)
        dat_bytes = len(raw) - original_fx_bytes + size
        steps.append(dict(looks=count, added=effects[count - 1]['name'] if count > 10 else None,
                          capacities=cap, effect_bytes=size, dat_bytes=dat_bytes,
                          main_request=7628 + align4(dat_bytes + u32(raw, 116))))
    savings = []
    for i, effect in enumerate(effects):
        cap, size = pool_layout(effects[:i] + effects[i + 1:], builtin)
        savings.append(dict(name=effect['name'], bytes_saved=fx_bytes - size, capacities_after_removal=cap))
    save(HERE / 'evidence/data-budget.json', dict(status='PASS', layouts=steps, removal_savings=savings,
         original_fx_bytes=original_fx_bytes, final_fx_bytes=fx_bytes,
         padding_reclaimed_at_original_10=original_fx_bytes - steps[0]['effect_bytes']))
    shutil.copyfile(ROOT / 'research/g154/layout.json', HERE / 'layout.json')
    print(json.dumps(dict(status='PASS', looks=18, capacities=caps, fx_bytes=fx_bytes, files=changes)))


if __name__ == '__main__':
    main()
