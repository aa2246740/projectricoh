"""Emulator check: which task runs at the H01/H06/H07/H08 hook sites, against the kernel word 0x200D1838.

Usage: TMPDIR=/Volumes/Workspace/Scratch/tmp/projectricoh/diag146-finish \
       /usr/bin/python3 -I -B research/unit28_stock/emu_g146_hooks.py <run-name>

tools/gxr_emulator is used, not modified. The run resumes the M2d final UI checkpoint
research/emulator_m2d/local/record-cold-final-r11-stop.pkl (official 1.51 ilaunch3, UI state 2, Task 6 at its
queue 1 receive; SHA-checked as tools/gxr_emulator/input_run.py machine_from() does, the medium copied into the
run directory) and presses keys through tools/gxr_emulator/panel.py. The hook sites are the v3.8 patch sites
(firmware/resident_v38/local/resident/hooks.json; their original bytes equal the 1.51 image):
  H01 0x2028709C menu_open, H06 0x202BE24C panel_open, H07 0x202871D8 event, H08 0x202BB968 apply_step.
At every hit the DAT's note_task() source (the halfword 0x200D1838) is compared with an independent source:
the kernel dispatcher's own last switch target (r9 at 0x0500C92C, where the dispatcher loads that task's saved
SPU from the task table 0x200D2174), the SPU at the hit against the per-task SPU values seen at dispatch, the
task state word 0x200D2594+4*(task-1), and PSW.SM (1 = task stack, 0 = interrupt stack).
Control sites (not hooks, same Task 6 UI code path): 0x202B0B18 ui-event, 0x202AFE98 ui-key-map; they show the
comparison works where the hooks are not reached.
Writes only research/emulator_m2d/local/unit28-g146/<run-name>/ and TMPDIR.
"""
import json
import os
import shutil
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = ROOT / 'research/emulator_m2d/local/unit28-g146' / sys.argv[1]
EMU = ROOT / 'tools/gxr_emulator'
sys.path.insert(0, str(EMU))
from m2 import restore                                    # noqa: E402
from observe import Observer                              # noqa: E402
from panel import Panel                                   # noqa: E402
from storage_run import Machine, sha                      # noqa: E402

assert Path(os.environ['TMPDIR']) == Path('/Volumes/Workspace/Scratch/tmp/projectricoh/diag146-finish')
CHECKPOINT = ROOT / 'research/emulator_m2d/local/record-cold-final-r11-stop.pkl'
HOOKS = {0x2028709C: 'H01', 0x202BE24C: 'H06', 0x202871D8: 'H07', 0x202BB968: 'H08'}
CONTROLS = {0x202B0B18: 'ui-event', 0x202AFE98: 'ui-key-map'}
CURRENT, STATE, SAVED_SP = 0x200D1838, 0x200D2594, 0x200D2174
SEGMENTS = [('ADJ', 300000, 3000000), ('OK', 300000, 1500000), ('DISP', 300000, 1500000),
            ('UP', 300000, 1500000), ('DOWN', 300000, 1500000), ('LEFT', 300000, 1500000),
            ('RIGHT', 300000, 1500000), ('ADJ', 300000, 3000000)]


def main():
    OUT.mkdir(parents=True, exist_ok=False)
    result = dict(checkpoint=str(CHECKPOINT.relative_to(ROOT)), hooks={hex(k): v for k, v in HOOKS.items()},
                  controls={hex(k): v for k, v in CONTROLS.items()})
    started = time.monotonic()
    machine = None
    try:
        metadata = json.loads(CHECKPOINT.with_suffix('.json').read_text())
        if sha(CHECKPOINT) != metadata['sha256']:
            raise ValueError('checkpoint digest differs')
        result['checkpoint_sha256'] = metadata['sha256']
        import pickle
        state = pickle.loads(CHECKPOINT.read_bytes())
        record = next((d.get('medium_record') for d in state['devices'] if 'medium_record' in d), None)
        del state
        card = None
        if record:
            source = Path(record['path']).resolve()
            if sha(source) != record['sha256']:
                raise ValueError('checkpoint medium identity differs')
            card = OUT / 'medium.img'
            shutil.copyfile(source, card)
            result['medium'] = dict(source=str(source.relative_to(ROOT)), sha256=record['sha256'])
        machine = Machine(card=card)
        restore(machine.cpu, CHECKPOINT)
        base = machine.devices['monitor'].base
        machine.cpu.breakpoints = {a: f for a, f in machine.cpu.breakpoints.items() if base + 0x40 <= a <= base + 0x80}
        machine.cpu.write_traces.clear()
        machine.observer = Observer(machine.cpu)
        cpu = machine.cpu
        cpu.set_mode('fast')
        panel = Panel(cpu, machine.devices)
        panel.down = set(metadata.get('panel_down', []))
        panel.advance()
        previous = cpu.step_hook

        def step(c):
            panel.advance()
            previous(c)
        cpu.step_hook = step

        def u(address, size=4):
            return int.from_bytes(cpu.read(address, size), 'big')
        last = dict(task=None, spu=None, step=None)
        seen = {}

        def dispatched(c):
            last.update(task=c.get_reg('r9'), spu=c.get_reg('r8'), step=c.steps)
            seen.setdefault(c.get_reg('r9'), set()).add(c.get_reg('r8'))
        machine.observer.breakpoint(0x0500C92C, dispatched)
        hits = []

        def hit(label, kind):
            def fn(c):
                spu = c.get_reg('spu')
                word = u(CURRENT, 2)
                near = sorted(((min(abs(spu - s) for s in v), t) for t, v in seen.items()))[:3]
                row = dict(site=label, kind=kind, step=c.steps, pc=hex(c.get_reg('pc')), lr=hex(c.get_reg('lr')),
                           word_200d1838=word, dispatched_task=last['task'], dispatch_step=last['step'],
                           psw_sm=bool(c.get_reg('psw') & 0x80), spu=hex(spu),
                           nearest_dispatch_spu=[dict(task=t, distance=d) for d, t in near],
                           state_word=u(STATE + 4 * (word - 1)) if 1 <= word <= 44 else None)
                if last['task'] is None:
                    row['match'] = None          # no dispatch seen since the resume: undetermined, not a mismatch
                else:
                    row['match'] = (row['psw_sm'] and word == last['task'] and bool(near) and near[0][1] == word)
                if len(hits) < 400:
                    hits.append(row)
                counts[label] = counts.get(label, 0) + 1
            return fn
        counts = {}
        for address, label in HOOKS.items():
            machine.observer.breakpoint(address, hit(label, 'hook'))
        for address, label in CONTROLS.items():
            machine.observer.breakpoint(address, hit(label, 'control'))
        segments = []
        for key, down, up in SEGMENTS:
            for pressed, budget in ((True, down), (False, up)):
                panel.set_key(key, pressed)
                remaining, stop = budget, None
                while remaining:
                    stop = cpu.run(min(remaining, 1000000))
                    remaining -= min(remaining, 1000000)
                    if stop.reason != 'max_steps':
                        break
                segments.append(dict(key=key, pressed=pressed, steps=cpu.steps, stop=stop.reason,
                                     pc=hex(cpu.get_reg('pc'))))
                print('SEG', json.dumps(segments[-1]), json.dumps(counts), flush=True)
                if stop.reason != 'max_steps':
                    raise RuntimeError('run stopped: %s at %s' % (stop.reason, hex(cpu.get_reg('pc'))))
        result.update(segments=segments, hits=hits, counts=counts,
                      ui_state=u(0x205D9C00), table=hex(u(0x2037F800)),
                      reached={label: counts.get(label, 0) for label in HOOKS.values()},
                      compared={k: dict(match=sum(1 for h in hits if h['kind'] == k and h['match'] is True),
                                        mismatch=sum(1 for h in hits if h['kind'] == k and h['match'] is False),
                                        undetermined=sum(1 for h in hits if h['kind'] == k and h['match'] is None))
                                for k in ('hook', 'control')},
                      hits_recorded_all=len(hits) == sum(counts.values()))
        result['status'] = 'DONE'
    except Exception as error:
        result['status'] = 'INCOMPLETE'
        result['error'] = dict(type=type(error).__name__, message=str(error)[:400])
    finally:
        if machine is not None:
            machine.close()
        result['seconds'] = round(time.monotonic() - started, 1)
        (OUT / 'result.json').write_text(json.dumps(result, indent=2, default=str) + '\n')
        print('EMU_DONE', result['status'], json.dumps(result.get('error')), json.dumps(result.get('reached')),
              flush=True)
        (OUT / 'DONE').write_text(result['status'] + '\n')


if __name__ == '__main__':
    main()
