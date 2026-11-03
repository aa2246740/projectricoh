#!/usr/bin/python3 -I -B
"""Replay the review's history with the native allocator and a single parent."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import struct
import sys

ROOT = Path(__file__).resolve().parents[3]
SCRATCH = Path('/Volumes/Workspace/Scratch/tmp/projectricoh/v4-r3')
BEGIN, CAPACITY = 0x20704800, 262144


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output-dir', required=True)
    parser.add_argument('--result', required=True)
    args = parser.parse_args()
    output = Path(args.output_dir).resolve()
    result = Path(args.result).resolve()
    assert output.is_relative_to(SCRATCH)
    assert result.is_relative_to(ROOT / 'research/body_v4_design/r3')
    assert Path(os.environ['TMPDIR']).resolve() == SCRATCH
    assert os.environ.get('GXR_EMULATOR_BATCH') == '1'
    assert os.getpriority(os.PRIO_PROCESS, 0) >= 10
    output.mkdir(parents=True, exist_ok=True)
    signal.alarm(180)
    sys.path.insert(0, str(ROOT / 'tools/gxr_emulator_batch'))
    import outputs
    from backend import Backend
    from image import Image
    outputs.require(output)
    image = Image('official')
    runs = []
    for kind, requests in (
        ('r2_reference_single', [108124]),
        ('r2_separate_blocks', [8192, 99908]),
        ('r3_single_parent', [108112]),
        ('r3_parent_with_tail_budget', [108064]),
    ):
        with Backend(mode='fast') as cpu:
            cpu.set_batch(True)
            image.load(cpu)
            cpu.set_reg('sp', 0x206ffff0)
            calls = []

            def call(address, value=None):
                if value is not None:
                    cpu.set_reg('r4', value)
                stop = cpu.call(address, (), 0x0bad0000, 2000000)
                assert stop.reason == 'return', stop.to_dict()
                returned = cpu.get_reg('r0')
                calls.append(dict(entry=hex(address), argument=value,
                                  returned=hex(returned), steps=stop.steps))
                return returned

            def blocks():
                address = struct.unpack('>I', cpu.read(BEGIN, 4))[0]
                found, seen = [], set()
                while address:
                    assert BEGIN <= address < BEGIN + CAPACITY and address not in seen
                    seen.add(address)
                    following, state, span = struct.unpack('>IB3xI', cpu.read(address, 12))
                    assert state == 0 and span >= 12
                    found.append(dict(address=hex(address), span=span))
                    address = following
                return found

            call(0x200bbd98)
            temporary = [call(0x200bbe00, size) for size in (8560, 938, 8560)]
            held = [call(0x200bbe00, size) for size in
                    (32768, 32768, 32768, 16384, 16384, 938)]
            assert all(temporary + held)
            for pointer in temporary:
                call(0x200bbf20, pointer)
            workspace = call(0x2005bf5c, 608)
            assert workspace
            allocations = [call(0x2005bf5c, n) for n in requests]
            assert all(allocations)
            spans = [struct.unpack('>I', cpu.read(p - 4, 4))[0] for p in allocations]
            workspace_span = struct.unpack('>I', cpu.read(workspace - 4, 4))[0]
            free_before = blocks()
            if kind != 'r2_separate_blocks':
                cpu.add_breakpoint(0x200da6c8, lambda current: True)
            cpu.set_reg('r4', 0)
            stop = cpu.call(0x200da69c, (), 0x0bad0000, 2000000)
            consumer = dict(reason=stop.reason, pc=hex(stop.pc), steps=stop.steps,
                            detail=stop.detail, allocation_r9=hex(cpu.get_reg('r9')))
            if kind == 'r2_separate_blocks':
                assert stop.reason == 'fault' and cpu.get_reg('r4') == 0
                consumer['expected_null_write_counterexample'] = True
            else:
                pointer = cpu.get_reg('r9')
                assert stop.reason == 'breakpoint' and stop.pc == 0x200da6c8 and pointer
                assert bytes(cpu.read(pointer, 12368)) == bytes(12368)
                consumer.update(allocation_succeeded=True, native_clear_completed=True)
            assert cpu.batch_stats.get('batch-steps', 0) > 0
            runs.append(dict(layout=kind, requests=requests, block_spans=spans,
                             workspace_request=608, workspace_span=workspace_span,
                             own_span=sum(spans) + workspace_span,
                             free_before_consumer=free_before,
                             total_free=sum(b['span'] for b in free_before),
                             max_free=max(b['span'] for b in free_before),
                             consumer=consumer, calls=calls,
                             batch_stats=dict(cpu.batch_stats)))
    assert [r['own_span'] for r in runs] == [108756, 108744, 108744, 108696]
    assert [r['max_free'] for r in runs] == [17512, 11936, 17512, 17512]
    assert runs[2]['free_before_consumer'][0] == runs[0]['free_before_consumer'][0]
    with Backend(mode='fast') as cpu:
        cpu.set_batch(True)
        image.load(cpu)
        cpu.set_reg('sp', 0x206ffff0)
        def tail_call(address, value=None):
            if value is not None:
                cpu.set_reg('r4', value)
            stop = cpu.call(address, (), 0x0bad0000, 2000000)
            assert stop.reason == 'return', stop.to_dict()
            return cpu.get_reg('r0')
        tail_call(0x200bbd98)
        first = tail_call(0x2005bf5c, 632)
        barrier1 = tail_call(0x2005bf5c, 64)
        second = tail_call(0x2005bf5c, 108088)
        barrier2 = tail_call(0x2005bf5c, 64)
        assert first and second and barrier1 and barrier2
        tail_call(0x2005c038, first)
        tail_call(0x2005c038, second)
        workspace = tail_call(0x2005bf5c, 608)
        parent = tail_call(0x2005bf5c, 108064)
        actual_spans = [struct.unpack('>I', cpu.read(p-4, 4))[0] for p in (workspace, parent)]
        assert actual_spans == [644, 108100], actual_spans
        assert workspace == first and parent == second
        tail_example = dict(requests=[608, 108064], actual_spans=actual_spans,
                            unseparated_tail_per_block=24, total_span=sum(actual_spans),
                            batch_stats=dict(cpu.batch_stats))
    doc = dict(classification='native_instruction_design_example', image_sha256=image.sha256,
               mode='fast', batch=True, runs=runs, short_tail_example=tail_example,
               scope='The explicit history is a model condition. Camera reachability and final v4 are untested.',
               source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    encoded = json.dumps(doc, ensure_ascii=False, indent=2) + '\n'
    (output / 'native-heap.json').write_text(encoded)
    result.write_text(encoded)
    print(json.dumps(dict(layouts=len(runs), own_spans=[r['own_span'] for r in runs],
                          largest_free=[r['max_free'] for r in runs],
                          native_clear_for_r3=True)))
    signal.alarm(0)


if __name__ == '__main__':
    main()
