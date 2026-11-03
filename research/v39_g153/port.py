"""Reproduce the g152 to g153 source merge inside the permitted directories."""
from pathlib import Path
import datetime
import difflib
import hashlib
import json
import os
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
ENGINE = ROOT / 'firmware/engine_v62_g153'
BASE = ROOT / 'firmware/engine_v60_g152'
TMP = Path('/Volumes/Workspace/Scratch/tmp/projectricoh/g153/merge')


def replace(text, old, new, count=1):
    assert text.count(old) == count, (old, text.count(old))
    return text.replace(old, new)


def main():
    frozen = json.loads((HERE / 'frozen-inputs.json').read_text())
    core = Path('candidate/containers/product/src/firmware/engine/core/eng_core.c')
    for name, expected in frozen['files'].items():
        selected = name.startswith('firmware/engine_v60_g152/') or name.startswith('firmware/resident_v39/')
        if not selected or '/local/' in name or name == 'firmware/engine_v60_g152/' + str(core):
            continue
        if 'sha256' in expected:
            assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == expected['sha256'], name
    TMP.mkdir(parents=True, exist_ok=True)
    os.environ.update(TMPDIR=str(TMP), PYTHONDONTWRITEBYTECODE='1')
    adapter = Path('candidate/containers/product/adapter.c')
    target = TMP / adapter
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(BASE / adapter, target)
    patch = (ROOT / 'research/body_v39/port/dat-adapter.diff').read_text()
    patch = replace(patch, '_Static_assert(sizeof(Integrated)==3920,"adapter layout unchanged");',
                    '_Static_assert(KV_UI_TEXT==14,"effect line includes prefix and terminator");')
    (HERE / 'evidence/adapter-g152.diff').write_text(patch)
    result = subprocess.run(['/usr/bin/patch', '--fuzz=0', '-p1', '-i',
                             str(HERE / 'evidence/adapter-g152.diff')],
                            cwd=TMP, text=True, capture_output=True)
    (HERE / 'evidence/adapter-merge.log').write_text(result.stdout + result.stderr)
    assert result.returncode == 0, result.stdout + result.stderr
    (ENGINE / adapter).write_text(target.read_text().replace('(gen 149)', '(gen 153)'))
    services = ENGINE / 'candidate/engine_services'
    text = (BASE / 'candidate/engine_services/services.c').read_text()
    text = replace(text, 'if(op==2){r->grain=0;', 'if(op==2){')
    text = replace(text, 'r->flags|=RF_UNCERTAIN;r->grain=0;s->rpc_phase=1;',
                   'r->flags|=RF_UNCERTAIN;s->rpc_phase=1;')
    assert text == (ROOT / 'firmware/resident_v39/engine_services/services.c').read_text()
    # The source identity includes the companion generation so g151 and g153
    # cannot be paired across their two bodies. This adds no instructions.
    text = '/* v3.9 companion generation 153; grain state is owned by the DAT. */\n' + text
    (services / 'services.c').write_text(text)
    header = (BASE / 'candidate/engine_services/engine_services.h').read_text()
    header = replace(header, 'void es_grain_commit(RvRoot *,uint32_t,uint32_t);\n', '')
    (services / 'engine_services.h').write_text(header)
    body = HERE / 'local/body'
    for folder in (ENGINE / 'resident', body / 'resident', body / 'engine_services'):
        folder.mkdir(parents=True, exist_ok=True)
    canonical = ROOT / 'firmware/resident_v39'
    for source in (canonical / 'resident').iterdir():
        if source.is_file():
            shutil.copyfile(source, body / 'resident' / source.name)
            if source.name != 'build.py':
                shutil.copyfile(source, ENGINE / 'resident' / source.name)
    for source in services.iterdir():
        expected = (canonical / 'engine_services' / source.name).read_bytes()
        actual = source.read_bytes().split(b'\n', 1)[1] if source.name == 'services.c' else source.read_bytes()
        assert actual == expected
        shutil.copyfile(source, body / 'engine_services' / source.name)
    product = ENGINE / 'candidate/containers/product'
    for name, old in (
        ('src/firmware/card_container_v2/gate.c', 'build_number==152'),
        ('src/firmware/engine/core/eng_data.c', 'build_number==152'),
        ('ui_v2_data.c', 'build_number!=152'),
        ('pack.py', 'if build == 152:'),
    ):
        source = BASE / 'candidate/containers/product' / name
        (product / name).write_text(replace(source.read_text(), old, old.replace('152', '153')))
    source = (BASE / 'candidate/containers/product/looks_data.py').read_text()
    source = replace(source, 'CAPACITY=32', 'CAPACITY=10')
    source = replace(source, 'CAPS=(8,48,32,32)', 'CAPS=(8,28,32,32)')
    source = replace(source, 'assert len(out)==8000',
                     'assert len(out)==32+32*CAPACITY+sum(align4(n*s) for n,s in zip(CAPS,LENGTHS))')
    (product / 'looks_data.py').write_text(source)
    (ENGINE / 'candidate/build152.py').unlink(missing_ok=True)
    (ENGINE / 'candidate/build153.py').write_text(
        'from pathlib import Path\nimport runpy\n'
        "runpy.run_path(str(Path(__file__).resolve().parents[3] / 'research/v39_g153/build.py'), run_name='__main__')\n")
    changed = {}
    for path in sorted(ENGINE.rglob('*')):
        if not path.is_file() or 'local' in path.relative_to(ENGINE).parts:
            continue
        key = 'firmware/engine_v60_g152/' + str(path.relative_to(ENGINE))
        original = frozen['files'].get(key, {})
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if 'sha256' in original and original['sha256'] != digest:
            changed[str(path.relative_to(ENGINE))] = {
                'base_sha256': original['sha256'],
                'merged_sha256': digest,
            }
    expected_core = frozen['files']['firmware/engine_v60_g152/' + str(core)]['sha256']
    imported = HERE / 'evidence/p1-import.json'
    if imported.is_file():
        expected_core = json.loads(imported.read_text())['core_sha256']
    assert hashlib.sha256((ENGINE / core).read_bytes()).hexdigest() == expected_core
    merged = (ENGINE / adapter).read_text()
    assert 'id==RV_SETTINGS&&op==2&&(result==RV_OK||result==RV_VERIFY)' in merged
    assert 'n.ui.last_cur=n.ui.cur' in merged
    assert 'if(op==6){rv_irq_restore(irq);return RV_OK;}' in text
    receipt = dict(generation=153, K=10, row_capacities=[8,28,32,32],
                   service_source_generation_tag=True, services_equal_g151_except_tag=True,
                   core_matches_selected_snapshot=True, changed=changed)
    (HERE / 'evidence/merge.json').write_text(json.dumps(receipt, indent=2) + '\n')
    with (HERE / 'PROGRESS.md').open('a') as output:
        output.write(datetime.datetime.now(datetime.timezone.utc).isoformat() +
                     '：源合并完成。服务库语义等于 g151，新增 g153 源码身份标记用于两代交叉拒绝。K=10，行池容量 8/28/32/32。\n')
    print(json.dumps(receipt))


if __name__ == '__main__':
    main()
