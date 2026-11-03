"""List all hook plan call sites and all production StepHook constructors."""
import ast
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
TOOLS = ROOT / 'tools/gxr_emulator_batch'


def main():
    plans, constructors, skips = [], [], []
    for path in sorted(TOOLS.glob('*.py')):
        source = path.read_text()
        for node in ast.walk(ast.parse(source)):
            if not isinstance(node, ast.Call):
                continue
            function = node.func
            name = function.id if isinstance(function, ast.Name) else function.attr if isinstance(function, ast.Attribute) else None
            if name not in ('declared_plan', 'batch_plan', 'StepHook', 'batch_skip'):
                continue
            row = {'path': str(path.relative_to(ROOT)), 'line': node.lineno,
                   'source': ast.get_source_segment(source, node)}
            if name == 'StepHook':
                constructors.append(row)
            elif name == 'batch_skip':
                skips.append(row)
            else:
                plans.append(row)
    backend = TOOLS / 'backend.py'
    source = ROOT / 'research/unit28_stock/emu_g146_hooks.py'
    source_bytes = source.read_bytes()
    source_text = source_bytes.decode()
    panel_note = {'path': str(source.relative_to(ROOT)),
                  'sha256_at_read': hashlib.sha256(source_bytes).hexdigest(),
                  'lines': [{'line': number, 'text': text} for number, text in
                            enumerate(source_text.splitlines(), 1) if 78 <= number <= 86],
                  'scope': 'Read-only source observation; concurrent directory is not frozen.'}
    result = {'backend_sha256': hashlib.sha256(backend.read_bytes()).hexdigest(),
              'plan_calls': plans, 'skip_calls': skips, 'constructors': constructors,
              'plain_panel_source': panel_note}
    (HERE / 'local/static-audit.json').write_text(json.dumps(result, indent=2) + '\n')
    assert len(constructors) == 5
    hook_plans = [row for row in plans if row['path'].endswith('/backend.py')]
    assert len(hook_plans) == 3, hook_plans
    print(json.dumps({'hook_plan_calls': hook_plans, 'constructors': constructors}), flush=True)


if __name__ == '__main__':
    main()
