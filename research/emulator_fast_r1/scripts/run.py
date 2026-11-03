"""Identical cold MAIN workload for the baseline and the fast copy."""
import argparse
import cProfile
import hashlib
import json
import os
from pathlib import Path
import signal
import sys
import time
from collections import Counter

sys.path.insert(0, str(Path(__file__).resolve().parent))
from safety import ROOT, HERE, FAST, TEMP, enable
enable()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--impl', choices=('batch', 'standby', 'fast'), required=True)
    p.add_argument('--name', required=True)
    p.add_argument('--points', default='1000000,50000000')
    p.add_argument('--profile', action='store_true')
    p.add_argument('--hist', action='store_true')
    p.add_argument('--timeout', type=int, default=1200)
    a = p.parse_args()
    signal.alarm(a.timeout)
    assert a.name.replace('-', '').replace('_', '').isalnum()
    target = HERE / 'runs' / (a.name + '.json')
    assert not target.exists(), target
    tool = FAST if a.impl == 'fast' else ROOT / ('tools/gxr_emulator_' + a.impl)
    sys.path.insert(0, str(tool))
    import outputs
    import speed_snapshot as snap
    import backend
    histogram = Counter()
    if a.hist:
        original_bus = backend.Backend._bus
        def counted(cpu, opaque, pc, addr, n, ptr, writing):
            histogram[(pc, addr, n, bool(writing))] += 1
            return original_bus(cpu, opaque, pc, addr, n, ptr, writing)
        backend.Backend._bus = counted
    outputs.declare_media(TEMP)
    from dial import set_dial
    setup = time.perf_counter()
    machine = snap.Machine()
    c = machine.cpu
    c.set_mode('fast')
    c.set_batch(True)
    snap.attach_panel(machine)
    serial = machine.devices['serial']
    mask, level = serial.input_bytes.get(0, (0, 0))
    serial.input_bytes[0] = (mask | 2, level & ~2)
    set_dial(c, machine.devices, 2)
    result = dict(impl=a.impl, name=a.name, pid=os.getpid(), points={}, segments=[],
                  setup_seconds=time.perf_counter()-setup,
                  image_sha256=machine.image.sha256,
                  library_sha256=snap.sha(tool/'build/libgxr_m32r.dylib'),
                  nice=os.getpriority(os.PRIO_PROCESS, 0))
    print(json.dumps(dict(name=a.name, pid=os.getpid(), ready=True)), flush=True)
    profile = cProfile.Profile() if a.profile else None
    try:
        for point in map(int, a.points.split(',')):
            start = c.steps
            before = dict(c.batch_stats)
            load = list(os.getloadavg())
            t = time.perf_counter()
            process_t = time.process_time()
            if profile:
                profile.enable()
            stop = c.run(point-start)
            if hasattr(c,'materialize_native'):
                c.materialize_native()
            if profile:
                profile.disable()
            seconds = time.perf_counter()-t
            cpu_seconds = time.process_time()-process_t
            assert stop.reason == 'max_steps' and c.steps == point, stop.to_dict()
            segment = dict(start=start, end=point, seconds=seconds, cpu_seconds=cpu_seconds,
                           steps_per_second=(point-start)/seconds,
                           load_before=load, load_after=list(os.getloadavg()),
                           stats={k:v-before.get(k,0) for k,v in c.batch_stats.items()})
            result['segments'].append(segment)
            result['points'][str(point)] = dict(state=snap.state_hash(machine),
                  observations=snap.value_hash(snap.observer_data(machine)),
                  events=snap.value_hash(list(machine.events)),
                  pending=snap.value_hash(machine.pending_returns))
            print(json.dumps(dict(point=point, **segment)), flush=True)
            target.write_text(json.dumps(result, indent=2)+'\n')
        result['status'] = 'complete'
    except BaseException as exc:
        result['status'] = 'error'
        result['error'] = dict(type=type(exc).__name__, message=str(exc), steps=c.steps)
        raise
    finally:
        if getattr(c, '_native_clock', None) is not None:
            result['native_clock'] = c._native_clock.stats()
        if getattr(c, '_native_driver', None) is not None:
            result['native_machine'] = c._native_driver.stats()
        if a.hist:
            result['bus_histogram'] = [dict(pc=hex(pc),address=hex(addr),size=n,
                write=w,count=count) for (pc,addr,n,w),count in histogram.most_common()]
        if profile:
            profile.dump_stats(str(HERE/'runs'/(a.name+'.prof')))
        target.write_text(json.dumps(result, indent=2)+'\n')
        machine.close()
    signal.alarm(0)


if __name__ == '__main__':
    main()
