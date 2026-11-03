"""Copy the fixed base and apply the service ownership change."""
from pathlib import Path
import hashlib
import json
import shutil

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / 'research/g131_merge'
OLD = ROOT / 'firmware/engine_v49_knobs'
NEW = ROOT / 'firmware/engine_v51_g131'

def edit(path, before, after, count=1):
    text = path.read_text()
    assert text.count(before) == count, (str(path.relative_to(ROOT)), count)
    path.write_text(text.replace(before, after))

def main():
    assert not NEW.exists()
    shutil.copytree(OLD, NEW, ignore=shutil.ignore_patterns('local', '__pycache__'))
    for name in ('services.c', 'native_seed.c', 'engine_services.h'):
        relative = Path('candidate/engine_services') / name
        assert (OLD / relative).read_bytes() == (ROOT / 'firmware/engine_v48_own' / relative).read_bytes()
        shutil.copyfile(ROOT / 'firmware/engine_v50_h07' / relative, NEW / relative)
    adapter = NEW / 'candidate/containers/product/adapter.c'
    edit(adapter, 'n.context=c;n.api=services;n.request=*q;n.active=1;n.ui_failed=0;',
         'n.context=c;n.api=services;n.request=*q;n.active=1;n.ui_failed=0;\n    rv_settings_entry(RV_PTR(c->root_address),0);')
    for entry in (1, 6, 7, 8):
        edit(adapter, f'n.entry={entry};',
             f'n.entry={entry};rv_settings_entry(RV_PTR(n.context->root_address),n.entry);')
    for relative in ('candidate/containers/product/src/firmware/card_container_v2/gate.c',
                     'candidate/containers/product/src/firmware/engine/core/eng_data.c',
                     'candidate/containers/product/ui_v2_data.c'):
        p = NEW / relative
        text = p.read_text()
        assert text.count('129') == 1
        p.write_text(text.replace('129', '131'))
    edit(NEW / 'candidate/containers/product/pack.py', 'if build == 129:', 'if build == 131:')
    build = NEW / 'candidate/build129.py'
    (NEW / 'candidate/build131.py').write_text(build.read_text().replace('129', '131'))
    build.unlink()
    common = NEW / 'candidate/common.py'
    text = common.read_text().replace('engine_v49_knobs', 'engine_v51_g131').replace('gen 129', 'gen 131')
    common.write_text(text)
    source = ROOT / 'research/g129_knobs'
    for name in ('fences.py', 'package.py', 'host_check.py', 'host_engine.c', 'target_check.py',
                 'target_runner.c', 'layout.py', 'adapter_layout.c', 'product_checks.py'):
        text = (source / name).read_text()
        for before, after in (('engine_v49_knobs', 'engine_v51_g131'),
                              ('package_v36_g129', 'package_v36_g131'),
                              ('g129_knobs', 'g131_merge'), ('g129', 'g131'), ('G129', 'G131')):
            text = text.replace(before, after)
        (WORK / name).write_text(text)
    wrapper = (ROOT / 'research/g130_fix/run_existing.py').read_text()
    wrapper = wrapper.replace('engine_v50_h07', 'engine_v51_g131').replace('g130_fix', 'g131_merge').replace('g130', 'g131').replace('130', '131')
    wrapper = wrapper.replace("'engine_v48_own')", "'engine_v48_own', 'engine_v49_knobs')")
    wrapper = wrapper.replace('(122, 123, 124, 126, 127)', '(122, 123, 124, 126, 127, 129)')
    (WORK / 'run_existing.py').write_text(wrapper)
    (NEW / 'candidate/local/tmp').mkdir(parents=True)
    report = dict(copied_source_files=sum(p.is_file() for p in NEW.rglob('*')),
                  context_other_reads_or_writes=0, generation=131)
    (WORK / 'evidence/merge.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(dict(name='prepare', returncode=0, counts=report)))

if __name__ == '__main__':
    main()
