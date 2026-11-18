"""Admission gate for compute jobs: measured CPU idle + memory, not load average.

Owner-approved 2026-11-05. It only decides *when* and *how many* jobs run. It
never changes what a job computes, so results stay bit-identical.

Why not load1: on macOS the load average also counts threads blocked on I/O and
memory, so with load 11-14 the 10-core machine was still ~45-50% idle and our
queues sat paused.

Rules (owner's machine: 10 cores, 16 GB):
  * spare = idle_cores - RESERVE_CORES (keep two cores for the owner).
  * A queue may add at most ONE new process per call, and only if spare >= 1
    and memory free >= MEM_ADMIT. Callers sample again before the next one, so
    a newly started job is already visible as busy CPU.
  * Also require normal VM pressure (kern.memorystatus_vm_pressure_level == 1).
  * Never kill or pause running jobs; when the machine is busy we just stop
    admitting.
  * Timing / speed measurements must use quiet_for_timing() instead: they need
    an almost idle machine, otherwise the numbers are wrong.

Usage in a queue loop:
    import sys; sys.path.insert(0, '<repo>/tools'); import loadgate
    cap, info = loadgate.cap(len(running))      # fill running up to cap
For a single job that wants a worker count (old gate() style):
    n, info = loadgate.workers()                # n == 0 means defer
"""
import json
import os
import subprocess

RESERVE_CORES = 2.0
MEM_ADMIT = 25          # kern.memorystatus_level (% free); below this: no new jobs
PER_QUEUE_MAX = 6
LOAD_PANIC_PER_CORE = 3.0   # extreme backstop only: load1 > 3x cores -> no new jobs
QUIET_IDLE_CORES = 8.5      # timing runs need >= this many idle cores (of 10)
QUIET_MEM = 30


def _ncpu():
    return os.cpu_count() or 1


def cpu_idle_fraction(seconds=3):
    """Measured system-wide CPU idle fraction over `seconds` (macOS iostat)."""
    out = subprocess.run(['iostat', '-n', '0', '-c', '2', '-w', str(int(seconds))],
                         capture_output=True, text=True, timeout=seconds + 15).stdout
    last = [l for l in out.splitlines() if l.strip()][-1].split()
    return int(last[2]) / 100.0     # columns: us sy id 1m 5m 15m


def mem_free_percent():
    out = subprocess.run(['sysctl', '-n', 'kern.memorystatus_level'],
                         capture_output=True, text=True, timeout=10).stdout
    return int(out.strip())


def mem_pressure_level():
    """macOS VM pressure: 1 normal, 2 warn, 4 critical (kern.memorystatus_vm_pressure_level)."""
    out = subprocess.run(['sysctl', '-n', 'kern.memorystatus_vm_pressure_level'],
                         capture_output=True, text=True, timeout=10).stdout
    try:
        return int(out.strip())
    except ValueError:
        return 4


def sample(seconds=3):
    ncpu = _ncpu()
    idle = cpu_idle_fraction(seconds)
    return dict(ncpu=ncpu, idle=idle, idle_cores=round(idle * ncpu, 2),
                spare=round(idle * ncpu - RESERVE_CORES, 2),
                mem_free=mem_free_percent(), mem_pressure=mem_pressure_level(),
                load1=round(os.getloadavg()[0], 2))


def _admissible(info):
    # 2026-11-05 revision: also require normal VM pressure. Our own jobs (several GB each)
    # pushed the machine into WARN with heavy compression/swap while memorystatus_level
    # still read ~35-40%, and kernel_task burned >1 core compressing.
    return (info['spare'] >= 1 and info['mem_free'] >= MEM_ADMIT
            and info['mem_pressure'] == 1
            and info['load1'] <= LOAD_PANIC_PER_CORE * info['ncpu'])


def cap(running, per_queue_max=PER_QUEUE_MAX, seconds=3):
    """How many processes this queue may have running now (adds at most one)."""
    info = sample(seconds)
    ok = _admissible(info)
    info['admit'] = bool(ok and running < per_queue_max)
    info['cap'] = min(per_queue_max, running + 1) if info['admit'] else running
    return info['cap'], info


def workers(max_workers=PER_QUEUE_MAX, seconds=3):
    """Worker count for one job (old gate() style). 0 means defer and retry later."""
    info = sample(seconds)
    ok = _admissible(info)
    info['workers'] = max(1, min(max_workers, int(info['spare']))) if ok else 0
    return info['workers'], info


def quiet_for_timing(seconds=5):
    """True only when the machine is near idle; required for speed measurements."""
    info = sample(seconds)
    info['quiet'] = (info['idle_cores'] >= QUIET_IDLE_CORES and info['mem_free'] >= QUIET_MEM
                     and info['mem_pressure'] == 1)
    return info['quiet'], info


if __name__ == '__main__':
    c, info = cap(0)
    print(json.dumps(info, ensure_ascii=False))
