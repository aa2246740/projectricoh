"""Check the physical MENU/OK key separately from item and value pages."""
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
from runtime import Runtime
from accept import check


def main():
    rows = []
    for version, tree, elf_name in [('g154', 'engine_v63_g154', 'full-r13'), ('g155b', 'engine_v66_g155b', 'boot-on')]:
        for page in ['items', 'value']:
            name = 'menu-ok-'+version+'-'+page
            source = HERE/'local'/('resume-'+version+'-hcb-final.pkl.z')
            engine = ROOT/'firmware'/tree
            elf = engine/'candidate/local'/elf_name/'engine.elf'
            r = Runtime(source, name, engine, elf)
            result = dict(status='OPEN', layer='模拟器实测', version=version, page=page,
                physical_key='MENU/OK, raw 24, native press 0x23', native_state_presets=[])
            try:
                if page == 'value':
                    r.key('DISP')
                result['before'] = r.state('before-menu-ok')
                r.key('MENU')
                for _ in range(20):
                    if r.u(0x205d9c00) == 5:
                        break
                    r.run(5_000_000)
                result['after'] = r.state('viewfinder')
                assert result['after']['state'] == 5 and result['after']['activity'] == 0
                assert result['after']['record'] == result['before']['record']
                assert result['after']['engine_levels'] == result['before']['engine_levels']
                assert r.u(r.u(0x200c0dac)+0x36e, 1) == 1
                result['settings'] = r.settings('viewfinder')
                saved = r.save('viewfinder')
                result['snapshot'] = saved
                proof, target = check(ROOT/saved['path'], engine, elf)
                result['complete_state'] = proof
                result['status'] = 'PASS'
            finally:
                result.update(inputs=r.inputs, events=r.events, calls=r.calls)
                r.machine.close()
                output = HERE/'evidence'/(name+'.json')
                assert not output.exists()
                output.write_text(json.dumps(result, indent=2)+'\n')
            rows.append(dict(name=name, status=result['status']))
            print(json.dumps(rows[-1]), flush=True)
    (HERE/'evidence/menu-ok-recheck.json').write_text(json.dumps(dict(status='PASS', rows=rows), indent=2)+'\n')


if __name__ == '__main__':
    main()
