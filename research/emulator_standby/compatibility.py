#!/usr/bin/python3
"""Rerun the existing recovery procedure and one historical cold receipt."""
import argparse
import ast
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import signal
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
TEMP = Path('/Volumes/Workspace/Scratch/tmp/projectricoh/emulator-standby-r1')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def load_digest():
    path = ROOT / 'tools/gxr_emulator_standby/standby_run.py'
    spec = importlib.util.spec_from_file_location('standby_digest', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    from backend import REGS
    module.REGS = REGS
    return module.fingerprint


def recovery(args, digest):
    source = ROOT / 'research/body_v39/tests/recovery_path.py'
    tree = ast.parse(source.read_text(), filename=str(source))
    edits = []
    class Adapt(ast.NodeTransformer):
        def visit_Constant(self, node):
            if node.value == 'tools/gxr_emulator_batch':
                edits.append('tool import path')
                return ast.copy_location(ast.Constant(f'tools/gxr_emulator_{args.emulator}'), node)
            return node
        def visit_FunctionDef(self, node):
            if node.name != 'make_card':
                return self.generic_visit(node)
            class Medium(ast.NodeTransformer):
                def visit_Expr(self, item):
                    if isinstance(item.value, ast.Call) and isinstance(item.value.func, ast.Attribute) \
                            and isinstance(item.value.func.value, ast.Name) and item.value.func.value.id == 'subprocess':
                        edits.append('omit git-ignore check for task scratch medium')
                        return None
                    return self.generic_visit(item)
                def visit_Call(self, item):
                    if isinstance(item.func, ast.Attribute) and item.func.attr == 'relative_to':
                        edits.append('absolute scratch medium path')
                        return ast.copy_location(item.func.value, item)
                    return self.generic_visit(item)
            return Medium().visit(node)
    tree = ast.fix_missing_locations(Adapt().visit(tree))
    module = {'__file__':str(source), '__name__':'recovery_task_adapter'}
    exec(compile(tree, str(source), 'exec'), module)
    module['LOCAL'] = TEMP / args.name
    module['HERE'] = HERE / 'tests'
    original = module['Machine']
    final = {}
    class RecordedMachine(original):
        def close(self):
            final.update(full_state=digest(self.cpu, normalize_medium=True), batch_stats=dict(self.cpu.batch_stats),
                         pc=hex(self.cpu.get_reg('pc')), state=int.from_bytes(self.cpu.read(0x205d9c00,4),'big'))
            super().close()
    module['Machine'] = RecordedMachine
    values = SimpleNamespace(image=str(args.image), label=args.name, elf=None, hold=[15],
                             serial=['8=0x5'], card='official', budget=150_000_000,
                             stop_at='confirm', confirm_keys=[])
    module['run'](values)
    target = HERE / 'evidence' / f'recovery-{args.name}.json'
    result = json.loads(target.read_text())
    result.update(final, adapter_edits=edits, original_script_sha256=sha(source.read_bytes()),
                  adapter_sha256=sha(Path(__file__).read_bytes()), emulator=args.emulator,
                  model_enabled=False, timeout=7200, nice=os.getpriority(os.PRIO_PROCESS,0))
    result['state_digest_normalization'] = ['SdHost.medium_record.path; content hash retained']
    result['historical_receipt'] = 'research/body_v39/evidence/recovery-official-confirm.json'
    result['historical_step_equal'] = result['steps'] == 65_975_242
    target.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(dict(name=args.name, steps=result['steps'], digest=result['full_state']['sha256'],
                          historical_step_equal=result['historical_step_equal'])), flush=True)


def cold(args, digest):
    from storage_run import Machine
    from panel import Panel
    from dial import set_dial
    from input_run import Flow
    machine = Machine()
    cpu = machine.cpu
    cpu.set_mode('fast')
    cpu.set_batch(True)
    serial = machine.devices['serial']
    mask, level = serial.input_bytes[0]
    serial.input_bytes[0] = (mask | 2, level & ~2)
    set_dial(cpu, machine.devices, 2)
    panel = Panel(cpu, machine.devices)
    panel.chain(cpu)
    flow = Flow(machine, [], [])
    for address in (0x202b12a4, 0x2026580c, 0x2017098c, 0x20173a10, 0x20173a64):
        flow.observer.breakpoint(address, flow.point(f'watch-{address:08x}'))
    old = cpu.breakpoints.get(0x20069160)
    def ready(c):
        if old:
            old(c)
        return bool(c.get_reg('psw') & 0x80 and machine.task() == 6)
    cpu.add_breakpoint(0x20069160, ready)
    try:
        stop = cpu.run(50_000_000)
        historical = json.loads((ROOT/'research/emulator_m2d/local/record-cold-final-r11.json').read_text())
        result = dict(name=args.name, emulator=args.emulator, model_enabled=False,
                      steps=cpu.steps, stop=stop.to_dict(), state=int.from_bytes(cpu.read(0x205d9c00,4),'big'),
                      full_state=digest(cpu), batch_stats=dict(cpu.batch_stats),
                      flow_counts=dict(flow.counts), flow=flow.rows,
                      observations=machine.observer.summary(), board_events=machine.devices['board'].events,
                      historical_receipt='research/emulator_m2d/local/record-cold-final-r11.json',
                      historical_sha256=sha((ROOT/'research/emulator_m2d/local/record-cold-final-r11.json').read_bytes()),
                      historical_equal=dict(steps=cpu.steps == historical['steps'],
                                            pc=stop.pc == historical['stop']['pc'],
                                            flow_counts=dict(flow.counts) == historical['flow_counts']),
                      image_sha256=machine.image.sha256, timeout=7200,
                      nice=os.getpriority(os.PRIO_PROCESS,0))
        (HERE/'evidence'/f'cold-{args.name}.json').write_text(json.dumps(result, indent=2)+'\n')
        print(json.dumps(dict(name=args.name, steps=cpu.steps, state=result['state'],
                              historical_equal=result['historical_equal'], digest=result['full_state']['sha256'])), flush=True)
    finally:
        machine.close()


def window(args, digest):
    """Recreate the deleted temporary body, then run the original cold check."""
    sys.path.insert(0, str(ROOT/'research/review_body_v39/checks'))
    import static_check as static
    folder = ROOT/'research/v310_window/options/baseline'
    body = static.rebuild((ROOT/'artifacts/firmware/gxr-1.51/ilaunch3').read_bytes(),
                          static.Elf(folder/'build/resident.elf'),
                          json.loads((folder/'patch-manifest.json').read_text()))
    expected = json.loads((ROOT/'research/v310_window/evidence/fixture-baseline.json').read_text())
    assert sha(body) == expected['body_sha256']
    image = TEMP/(args.name+'-historical-baseline.bin')
    image.write_bytes(body)
    source = ROOT/'research/v310_window/cold_check.py'
    tree = ast.parse(source.read_text(), filename=str(source))
    class Adapt(ast.NodeTransformer):
        def visit_Constant(self, node):
            if node.value == 'tools/gxr_emulator_batch':
                return ast.copy_location(ast.Constant(f'tools/gxr_emulator_{args.emulator}'),node)
            return node
    tree = ast.fix_missing_locations(Adapt().visit(tree))
    module = {'__file__':str(source), '__name__':'historical_cold_adapter'}
    exec(compile(tree,str(source),'exec'),module)
    module['TEMP'] = TEMP
    module['HERE'] = HERE/args.name
    fixture = dict(expected, body=str(image))
    module['F'].prepare = lambda name: fixture
    import storage_run
    original = storage_run.Machine
    final = {}
    class RecordedMachine(original):
        def close(self):
            final.update(full_state=digest(self.cpu))
            super().close()
    storage_run.Machine = RecordedMachine
    os.environ['V310_COLD_BUDGET'] = '50000000'
    failure = None
    try:
        module['run']('baseline')
    except AssertionError as exc:
        failure = str(exc)
    result = json.loads((module['HERE']/'evidence/baseline/cold-incomplete.json').read_text())
    historical = json.loads((ROOT/'research/v310_window/evidence/baseline/cold-incomplete.json').read_text())
    keys = ('stop','state','observed','dma_lengths','ready_notifications_released','batch_stats')
    result.update(final, name=args.name, emulator=args.emulator, model_enabled=False,
                  expected_incomplete_assertion=failure,
                  historical_receipt='research/v310_window/evidence/baseline/cold-incomplete.json',
                  historical_equal={k:result[k] == historical[k] for k in keys},
                  original_script_sha256=sha(source.read_bytes()), adapter_sha256=sha(Path(__file__).read_bytes()))
    (HERE/'evidence'/f'window-{args.name}.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(name=args.name, steps=result['stop']['steps'],state=result['state'],
                          historical_equal=result['historical_equal'],digest=result['full_state']['sha256'])),flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--emulator', choices=('batch','standby'), required=True)
    parser.add_argument('--case', choices=('recovery','cold','window'), required=True)
    parser.add_argument('--image', type=Path, default=ROOT/'artifacts/firmware/gxr-1.51/ilaunch3')
    parser.add_argument('--name', required=True)
    args = parser.parse_args()
    assert Path(os.environ['TMPDIR']).resolve() == TEMP
    assert args.name.replace('-','').isalnum()
    assert os.getpriority(os.PRIO_PROCESS,0) >= 10
    sys.path.insert(0, str(ROOT/f'tools/gxr_emulator_{args.emulator}'))
    import backend, storage_run
    digest = load_digest()
    sys.path.insert(0, str(ROOT/f'tools/gxr_emulator_{args.emulator}'))
    signal.alarm(7200)
    try:
        {'recovery':recovery, 'cold':cold, 'window':window}[args.case](args, digest)
    finally:
        signal.alarm(0)
