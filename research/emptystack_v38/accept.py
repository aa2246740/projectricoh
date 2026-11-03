from pathlib import Path
import json
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from scope import ROOT, WORK, LOCAL, setup, save, sha
from build_tools import load, bind
from run_existing import relocate

def module():
    old = load(ROOT / 'research/g135_v37/accept.py', 'accept137_base')
    for value in vars(old).values():
        if callable(value) and hasattr(value, '__code__') and value.__module__ == old.__name__:
            value.__code__ = relocate(value.__code__)
    old.HERE = WORK
    old.PACKAGE = ROOT / 'firmware/package_v38_g137/local/SD_ROOT'
    old.BODY = old.PACKAGE / 'ilaunch3'
    old.DAT = old.PACKAGE / 'GXRCE.DAT'
    old.RESIDENT = ROOT / 'firmware/resident_v38/local/resident/build/resident.elf'
    old.ENGINE = ROOT / 'firmware/engine_v54_g137/candidate/local/full-r13/engine.elf'
    old.GENERATION = 137
    old.freeze = lambda: None
    old.save = lambda name, value: save(WORK / name, value)
    return old

def main():
    setup()
    unit = sys.argv[1]
    old = module()
    if len(sys.argv) > 2 and sys.argv[2] == 'part1':
        sys.argv = [__file__, unit]
        old.main()
        return
    m, h, p, w = old.boot(unit)
    result = {'types': [type(x).__name__ for x in (m, h, p, w)],
              'm_functions': sorted(k for k, v in vars(m).items() if callable(v)),
              'p_functions': [k for k in dir(p) if not k.startswith('_')],
              'h_functions': [k for k in dir(h) if not k.startswith('_')],
              'state': old.snapshot(h)}
    save(LOCAL / ('boot-api-' + unit + '.json'), result)
    print(json.dumps(result, default=str))

if __name__ == '__main__':
    main()
