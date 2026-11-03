#!/usr/bin/python3
"""Check final cold results and keep inherited recovery coverage explicit."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import struct
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BODY = ROOT / 'research/v310_body'
sys.path.insert(0, str(HERE))
from audit import snapshot, memory


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def load_aliases():
    sys.path.insert(0, str(ROOT / 'tools/gxr_emulator_standby'))
    for stem in ('preview_link', 'nand_word', 'sd_long_response', 'nand_read_tail'):
        name = 'review_extra_' + stem
        path = BODY / 'fix/emulator' / (stem + '.py')
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)


def main():
    assert os.getpriority(os.PRIO_PROCESS, 0) >= 10
    target = HERE / 'evidence/final-behaviour-checks.json'
    assert not target.exists()
    load_aliases()
    rows = []
    for name, selector, zero in (('valid-look-mount-batch', 1, False), ('non-pure03-mount-batch', 3, True)):
        run = json.loads((HERE / 'evidence' / (name + '.json')).read_text())
        assert run['status'] == 'PASS'
        calls = [v for v in run['engine_calls'] if v['operation'] == 257]
        assert len(calls) == 1 and 'end' in calls[0]
        call = calls[0]
        assert call['before_context'] == dict(mode=0, my=0, pending=0, state=5, activity=0,
            S_selector=selector, S_white_balance='0909')
        path = ROOT / run['diagnostic']['snapshot']
        assert sha(path.read_bytes()) == run['diagnostic']['snapshot_sha256']
        state = snapshot(path)['cpu']
        u = lambda at, n=4: int.from_bytes(memory(state, at, n), 'big')
        assert u(0x200547ec) == 2 and u(0x20054706, 1) == 0
        S = u(0x200c0dac)
        settings = memory(state, S, 4096)
        assert settings[0x36e] == selector
        if zero:
            assert run['rpc_write_count'] == 0 and not run['BOOT_S_writes']
            assert run['extra']['BOOT_zero_colour_writes']
            assert call['before_S_sha256'] == sha(settings)
            assert bytes.fromhex(call['reply'])[28:32] == (2).to_bytes(4, 'big')
        else:
            target_bytes = (BODY / 'fix/local/mount-look-target.bin').read_bytes()
            dat = (ROOT / 'firmware/package_v310_g155b_test/GXRCE.DAT').read_bytes()
            base = u(0x20054770) - int.from_bytes(dat[132:136], 'big')
            g = 0x15f3c
            assert memory(state, base + g + 1461, 552) == target_bytes
            assert run['extra']['unit_T_equal_target'] and len(run['extra']['nine_rows']) == 9
            assert run['extra']['cycle_status'] == 'PASS' and run['extra']['later_BOOT_calls'] == 0
            assert run['rpc_write_count'] > 0
        rows.append(dict(case=name, complete_steps=run['steps'], selector_at_BOOT=selector,
            qualification_context_actual=True, BOOT_calls=1, BOOT_returned=True,
            word=2, inflight=0, zero_colour_writes=zero,
            snapshot_sha256=sha(path.read_bytes())))
    coverage = []
    for flow in ('official', 'v310'):
        source = BODY / 'fix/r3/local' / ('recovery-fixed-' + flow + '-TAA-20261103-final-state.pkl.z')
        saved = snapshot(source)
        counts = saved['reference']['counts']
        relevant = {k: v for k, v in counts.items() if 'resident' in k or k.startswith('hook-word ')}
        assert not any(relevant.values())
        coverage.append(dict(flow=flow, source_sha256=sha(source.read_bytes()),
            nonzero_resident_or_hook_counts=relevant,
            scope='Independently reread retained full-run coverage; not an independently repeated full prefix'))
    result = dict(status='PASS', cold_cases=rows, retained_recovery_coverage=coverage,
        fresh_tail_coverage='The independent tails directly counted H50/H51/H52 and one resident start address; full-window coverage belongs to the retained full runs',
        normalized_invalid_fixture='Selector 2 became 1 before BOOT in the earlier runs. Their 300M budgets did not test a non-04 gate and are not used as a failure result.',
        runner_sha256=sha(Path(__file__).read_bytes()))
    target.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(dict(status='PASS', cold_cases=len(rows), recovery_coverage=len(coverage))))


if __name__ == '__main__':
    main()
