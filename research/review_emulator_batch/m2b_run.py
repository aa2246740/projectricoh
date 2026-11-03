"""Rerun M2b cold, continuation, card and the four original check groups."""
import importlib.util
import json
from pathlib import Path
import shutil
import sys
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = HERE / 'local/m2b'
TOOLS = ROOT / 'tools/gxr_emulator_batch'
sys.path.insert(0, str(HERE))
from scope_guard import enable, admit_medium
enable()
sys.path.insert(0, str(TOOLS))
import backend
import sdcard
import input_run
import storage_run
admit_medium(sdcard)
input_run.OUT = storage_run.OUT = OUT


def load(path):
    spec = importlib.util.spec_from_file_location('review_' + path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    OUT.mkdir()
    stats = []
    original_init = backend.Backend.__init__
    original_run = backend.Backend.run

    def initialize(cpu, **kw):
        original_init(cpu, **kw)
        cpu.set_batch(True)
        stats.append(cpu.batch_stats)

    def run(cpu, budget):
        result = original_run(cpu, budget)
        if cpu.steps % 5000000 < budget:
            print(json.dumps({'steps': cpu.steps, 'stop': result.reason}), flush=True)
        return result
    backend.Backend.__init__ = initialize
    backend.Backend.run = run
    storage_run.Backend = lambda **kw: backend.Backend(**{'mode': 'fast', **kw})
    for name, resume, card, budget in [
        ('cold-review', None, None, 50000000),
        ('stable-review', OUT / 'cold-review-stop.pkl', None, 5000000),
        ('card-review', None, OUT / 'card-review.img', 55000000),
    ]:
        if card:
            shutil.copyfile(ROOT / 'research/emulator_speed/local/card-seed.img', card)
        args = SimpleNamespace(name=name, resume=resume, card=card, budget=budget,
                               segment=None, stop_at=[], stop_task=6, stop_after=[], watch=[])
        input_run.run(args)
    regression = load(ROOT / 'research/emulator_m2d/regression.py')
    regression.OUT, regression.TOOLS = OUT, TOOLS
    load_group = regression.load

    def group(name):
        module = load_group(name)
        if name == 'conformance':
            module.HERE = HERE / 'local/conformance'
            module.HERE.mkdir()
        return module
    regression.load = group
    previous = sys.argv
    sys.argv = [str(regression.__file__), 'regression-review']
    try:
        assert regression.main() == 0
    finally:
        sys.argv = previous
    checker = load(ROOT / 'research/emulator_batch/m2d_acceptance.py')
    checker.OUT = OUT
    result = checker.m2b(SimpleNamespace(cold='cold-review', stable='stable-review',
                                       card='card-review', regression='regression-review'))
    result.update(passed=sum(bool(v) for v in result['checks'].values()), total=len(result['checks']),
                  checker_sha256=storage_run.sha(Path(checker.__file__)),
                  checker_note='Original M2b assertions with batch source prefix and current batch library identity.')
    result['batch_stats'] = [{k: v for k,v in s.items()} for s in stats]
    result['status'] = 'passed' if result['passed'] == result['total'] else 'failed'
    (OUT / 'm2b-review.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'passed': result['passed'], 'total': result['total'], 'status': result['status']}), flush=True)
    assert result['status'] == 'passed'


if __name__ == '__main__':
    main()
