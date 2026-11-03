from pathlib import Path
import sys
import types
sys.path.insert(0, str(Path(__file__).resolve().parent))
from scope import ROOT, WORK, setup, neutral
import fences
from build_tools import load
from run_existing import relocate

def main():
    setup()
    stage = sys.argv[1]
    old_dir = ROOT / 'research/g135_v37'
    paths = {'host': 'host_check.py', 'layout': 'layout.py',
             'target': 'target_check.py', 'gate': 'target_gate.py',
             'words': 'verify_words.py', 'audit': 'audit_communications.py'}
    path = old_dir / paths[stage]
    module = load(path, 'stage137_' + stage)
    for name, value in list(vars(module).items()):
        if isinstance(value, Path):
            setattr(module, name, Path(str(value).replace(str(old_dir), str(WORK)).replace('engine_v53_g135', 'engine_v54_g137').replace('package_v37_g135', 'package_v38_g137')))
        elif isinstance(value, types.FunctionType) and value.__module__ == module.__name__:
            value.__code__ = relocate(value.__code__)
    sys.argv = [str(path)] + sys.argv[2:]
    module.main()

if __name__ == '__main__':
    main()
