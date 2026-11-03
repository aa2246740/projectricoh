from pathlib import Path
import hashlib
import json
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from scope import ROOT, WORK, LOCAL, setup, sha, save, neutral
from build_tools import load

def main():
    setup()
    helpers = load(ROOT / 'research/g135_v37/check_delta.py', 'code137_helpers')
    helpers.WORK = WORK
    baseline = ROOT / 'firmware/engine_v53_g135/candidate/local/full-r13/engine.elf'
    current = ROOT / 'firmware/engine_v54_g137/candidate/local/full-r13/engine.elf'
    old_compiled = helpers.compiled(baseline)[0]
    new_compiled = helpers.compiled(current)[0]
    common = sorted(old_compiled.keys() & new_compiled.keys())
    same = [name for name in common if old_compiled[name]['lines'] == new_compiled[name]['lines']]
    changed = [name for name in common if name not in same]
    source_changes = []
    allowed = {'owned','rv_view_owned','rv_ui_capture','ui_list','ui_view','uv_move','list_bind_impl',
               'kv_ui_move','kv_ui_render','gxr2_tweak_layout','eng_data_accept','uv_validate'}
    for item in json.loads((WORK / 'source-files.json').read_text()):
        before, after = ROOT / item['source'], ROOT / item['target']
        if before.suffix != '.c':
            continue
        old_functions = {name:value[0] for name,value in helpers.functions(neutral(before.read_text())).items()}
        new_functions = {name:value[0] for name,value in helpers.functions(after.read_text()).items()}
        for name in old_functions.keys() | new_functions.keys():
            if old_functions.get(name) != new_functions.get(name):
                source_changes.append({'path':item['target'],'function':name})
                assert name in allowed, ('Unplanned function difference', item['target'], name)
    critical = ['make_plan','write_word','apply_impl','kv_apply_work','kv_data_request','storage','settings']
    checked = {name:name in same for name in critical if name in common}
    assert len(checked)>=3 and all(checked.values()), checked
    legacy = load(ROOT / 'firmware/stage2l_switch/tools/build.py', 'code137_elf')
    image = legacy.Elf(current)
    raw = (current.parent / 'engine.bin').read_bytes()
    section = next(s for s in image.sections if s['name']=='.engine')
    assert image.content(section) == raw
    dat_path = ROOT / 'firmware/package_v38_g137/SD_ROOT/GXRCE.DAT'
    dat = dat_path.read_bytes()
    sections = [tuple(int.from_bytes(dat[128+12*i+j:132+12*i+j],'big') for j in (4,8)) for i in range(7)]
    assert dat[sections[0][0]:sections[0][0]+sections[0][1]] == raw
    result = {'status':'PASS_STATIC','dat_sha256':sha(dat_path),'elf_sha256':sha(current),
              'baseline_elf_sha256':sha(baseline),'common_functions':len(common),
              'same_skeletons':len(same),'changed_skeletons':changed,'critical':checked,
              'source_changes':source_changes,'section7_bytes':sections[6][1]}
    save(WORK / 'code-results.json',result)
    print(json.dumps({k:v for k,v in result.items() if k not in ('source_changes','changed_skeletons')}))

if __name__ == '__main__':
    main()
