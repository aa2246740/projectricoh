"""Run an existing entry by path, with isolated outputs and one worker."""
import argparse
import atexit
import builtins
import contextlib
import cProfile
import ctypes
import hashlib
import importlib
import io
import json
import os
from pathlib import Path
import resource
import runpy
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--side", choices=("old", "fast"), default="old")
    parser.add_argument("--name", required=True)
    parser.add_argument("--profile", action="store_true")
    parser.add_argument("--mode", choices=("all", "region", "prefix", "plain"), default="region")
    parser.add_argument('--child-only')
    parser.add_argument('--limit-seconds', type=float, default=0)
    parser.add_argument("entry", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    setup_start = time.perf_counter()
    runner_sha = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    folder = HERE / "local" / args.name
    folder.mkdir(parents=True, exist_ok=False)
    (folder/'process.json').write_text(json.dumps(dict(pid=os.getpid()))+'\n')
    native_folder = ROOT / 'tools/native_harness_fast/local/runs' / args.name
    native_folder.mkdir(parents=True)
    temporary = native_folder / 'temporary'
    temporary.mkdir()
    mapped = {}
    records = []
    child_calls = []
    cli_calls = []
    entry_symbols = []
    original_parse = argparse.ArgumentParser.parse_args
    def parse_cli(parser, *a, **kw):
        cli_calls.append(dict(options=[item.option_strings for item in parser._actions],
                              names=[item.dest for item in parser._actions]))
        return original_parse(parser, *a, **kw)
    argparse.ArgumentParser.parse_args = parse_cli
    original_run = subprocess.run
    original_popen = subprocess.Popen
    original_dlopen = ctypes._dlopen
    ctypes._dlopen = lambda name, mode: original_dlopen(str(path_for(name)) if name else name, mode)
    def run_child(command, *a, **kw):
        before = resource.getrusage(resource.RUSAGE_CHILDREN)
        begin = time.perf_counter()
        is_python = Path(str(command[0])).name.startswith('python')
        if is_python and ('-c' in command or any(str(x).endswith('.py') for x in command[1:])):
            # Run Python entries in this worker so the same pins and output
            # rules apply to the complete group, including nested entries.
            saved_argv, saved_path = sys.argv, sys.path[:]
            out, err = io.StringIO(), io.StringIO()
            status = 0
            try:
                with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                    if '-c' in command:
                        index = command.index('-c')
                        sys.argv = ['-c']+list(command[index+2:])
                        exec(command[index+1], {'__name__':'__main__', '__builtins__':builtins})
                    else:
                        index = next(i for i,x in enumerate(command) if str(x).endswith('.py'))
                        sys.argv = list(command[index:])
                        call_count = sum(t['name'] in ('call', 'interpreter_call') for t in timed)
                        target = Path(str(command[index]))
                        if args.child_only and target.name == 'safety_cases.py':
                            command = list(command)+['--only', args.child_only]
                        wrapper = Path(args.entry[0])
                        use_wrapper = wrapper.name == 'run_existing.py' and target.is_relative_to(ROOT/'research')
                        if use_wrapper:
                            sys.argv = [str(wrapper)]+(['--fast-crc'] if '--fast-crc' in args.entry else [])+list(command[index:])
                            outer_scope = runpy.run_path(str(ROOT/wrapper), run_name='__main__')
                            scopes = [value for value in outer_scope.values() if isinstance(value, dict)]
                            scopes += [getattr(value, '__globals__', {}) for value in outer_scope.values() if callable(value)]
                            candidates = [value for value in scopes if Path(str(value.get('__file__', ''))).name == target.name
                                          and callable(value.get('main'))]
                            scope = candidates[0] if candidates else {}
                        else:
                            scope = runpy.run_path(str(target), run_name='__main__')
                        entry_symbols.append(dict(name=Path(str(command[index])).name,
                                                  module=scope.get('__name__'),
                                                  functions=[k for k,v in scope.items()
                                                             if callable(v) and not k.startswith('_')]))
                        if (Path(str(command[index])).name in ('ui_acceptance.py', 'view_reentry.py', 'safety_cases.py')
                                and call_count == sum(t['name'] in ('call', 'interpreter_call') for t in timed)
                                ):
                            if not callable(scope.get('main')):
                                raise RuntimeError('entry namespace unavailable')
                            sys.argv = list(command[index:])
                            value = scope['main']()
                            status = value if isinstance(value, int) else 0
            except SystemExit as exc:
                status = exc.code if isinstance(exc.code, int) else int(bool(exc.code))
            except Exception as exc:
                status = 99
                err.write(type(exc).__name__)
                records.append(dict(type=type(exc).__name__, message=str(exc)[:200]))
            finally:
                sys.argv, sys.path[:] = saved_argv, saved_path
            text_mode = kw.get('text', False) or kw.get('universal_newlines', False) or kw.get('encoding')
            stdout, stderr = out.getvalue(), err.getvalue()
            if not text_mode:
                stdout, stderr = stdout.encode(), stderr.encode()
            result = subprocess.CompletedProcess(command, status, stdout, stderr)
            if kw.get('check') and status:
                raise subprocess.CalledProcessError(status, command, output=stdout, stderr=stderr)
        else:
            command = list(command)
            command = [str(path_for(x)) if isinstance(x, (str, Path)) and str(x).startswith('/')
                       else x for x in command]
            if '-o' in command:
                index = command.index('-o')+1
                command[index] = str(path_for(command[index], True))
            environment = dict(kw.get('env') or os.environ)
            environment['TMPDIR'] = str(temporary)
            kw['env'] = environment
            saved_popen = subprocess.Popen
            subprocess.Popen = original_popen
            try:
                result = original_run(command, *a, **kw)
            finally:
                subprocess.Popen = saved_popen
        after = resource.getrusage(resource.RUSAGE_CHILDREN)
        names = [Path(str(item)).name for item in command if str(item).endswith('.py')]
        child_calls.append(dict(name=Path(str(command[0])).name, entries=names,
                                returncode=result.returncode, wall=time.perf_counter()-begin,
                                cpu=after.ru_utime+after.ru_stime-before.ru_utime-before.ru_stime))
        return result
    subprocess.run = run_child
    original_open = builtins.open
    original_io_open = io.open
    original_mkdir = Path.mkdir
    original_path_open = Path.open
    accessor = Path('.')._accessor
    original_accessor_open = accessor.open
    original_import = builtins.__import__
    original_addaudit = sys.addaudithook
    # The enclosing OS profile owns this run's narrower write roots.
    # Historical entries request a different output root in their audit hooks.
    sys.addaudithook = lambda hook: None
    old_roots = (ROOT / "tools/native_harness", ROOT / "research", ROOT / "firmware")

    def path_for(path, writing=False):
        if isinstance(path, int):
            return path
        p = Path(path).absolute()
        if p.is_relative_to(HERE) or p.is_relative_to(ROOT / "tools/native_harness_fast"):
            if writing and p.name == 'scenarios.json' and p.is_relative_to(ROOT/'tools/native_harness_fast/local'):
                mapped[str(p)] = p
            return p
        if writing:
            if p.suffix == ".py":
                raise PermissionError("source copy is outside this run")
            key = str(p)
            if key not in mapped:
                destination = native_folder if p.suffix in ('.dylib', '.bin', '.txt') else folder
                mapped[key] = destination / ("result_%04d" % len(mapped) + p.suffix)
            return mapped[key]
        return mapped.get(str(p), p)

    def open_file(file, mode="r", *a, **kw):
        return original_open(path_for(file, any(x in mode for x in "wax+")), mode, *a, **kw)

    def io_open(file, mode="r", *a, **kw):
        return original_io_open(path_for(file, any(x in mode for x in "wax+")), mode, *a, **kw)

    def path_open(path, mode='r', buffering=-1, encoding=None, errors=None, newline=None):
        return original_open(path_for(path, any(x in mode for x in 'wax+')), mode,
                             buffering=buffering, encoding=encoding, errors=errors, newline=newline)

    def mkdir(path, *a, **kw):
        p = Path(path).absolute()
        if p.is_relative_to(HERE) or p.is_relative_to(ROOT / "tools/native_harness_fast"):
            return original_mkdir(path, *a, **kw)
        return None

    def accessor_open(path, flags, mode=0o777):
        writing = bool(flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND))
        return original_accessor_open(path_for(path, writing), flags, mode)

    def import_module(name, *a, **kw):
        value = original_import(name, *a, **kw)
        if name.split('.')[-1] == 'support':
            accessor.open = accessor_open
            builtins.open, io.open, Path.open, Path.mkdir = open_file, io_open, path_open, mkdir
        return value

    builtins.open, io.open, Path.mkdir = open_file, io_open, mkdir
    Path.open = path_open
    builtins.__import__ = import_module
    sys.path.insert(0, str(ROOT / ("tools/native_harness" if args.side == "old" else "tools/native_harness_fast")))
    backend = importlib.import_module("python_backend")
    backend.CACHE = ROOT / "tools/native_harness_fast/local/decode"
    # Keep identical source listings for both sides; all generated bytes stay local.
    backend.CACHE.mkdir(parents=True, exist_ok=True)
    import harness
    import field_replay
    import product_execute
    if args.side == "fast":
        import prefix_cache
        prefix_cache.ENABLED = args.mode in ("all", "prefix")
        backend.REGION_CACHE = args.mode in ("all", "region")
        if not backend.REGION_CACHE:
            backend._cpu.reg = backend._original_reg
    timed = []
    forked = []
    child_context = None
    original_fork, original_exit = os.fork, os._exit

    def fork_worker():
        nonlocal child_context
        begin = time.perf_counter()
        offset = len(timed)
        pid = original_fork()
        if pid == 0:
            child_context = (begin, offset, time.process_time())
        else:
            forked.append(pid)
        return pid

    def exit_worker(status):
        if child_context:
            begin, offset, cpu_begin = child_context
            record = dict(returncode=status, wall=time.perf_counter()-begin,
                          cpu=time.process_time()-cpu_begin, timings=timed[offset:])
            if args.side == 'fast':
                record['cache'] = prefix_cache.STATS
            with original_open(folder / ('child_%d.json' % os.getpid()), 'w') as stream:
                json.dump(record, stream)
        original_exit(status)

    os.fork, os._exit = fork_worker, exit_worker

    def measure(owner, name):
        fn = getattr(owner, name)

        def measured(*a, **kw):
            label = name
            if owner is backend.PythonBackend:
                label = 'interpreter_call'
            elif owner is product_execute.RpcEdge:
                label = 'rpc'
            state_before = None
            if name == 'publish':
                state_before = a[0].u(product_execute.ROOT_ADDR+5, 1)
                label = 'first_publish' if not a[1].image_base else 'later_publish'
            start = time.perf_counter()
            cpu = time.process_time()
            value = None
            try:
                value = fn(*a, **kw)
                return value
            finally:
                event = dict(name=label, wall=time.perf_counter()-start,
                                  cpu=time.process_time()-cpu,
                                  steps=getattr(value, 'steps', None), state_before=state_before)
                if name == 'publish':
                    event['crc_leaf_calls'] = a[0].stub_hits.get('gxr2_crc_add', 0)
                    event['crc_fast'] = a[1].crc_fast
                timed.append(event)
        setattr(owner, name, measured)

    for name in ("__init__", "prepare_menu", "leave_other_list", "open_image_settings"):
        measure(harness.Harness, name)
    measure(field_replay, "publish")
    measure(field_replay, "boot")
    measure(product_execute.RpcEdge, "call")
    original_native = product_execute.Product._native
    def native_edge(product, address, name, fn):
        def observed(b):
            begin, cpu_begin = time.perf_counter(), time.process_time()
            try:
                return fn(b)
            finally:
                timed.append(dict(name='device_callback', wall=time.perf_counter()-begin,
                                  cpu=time.process_time()-cpu_begin, steps=None))
        return original_native(product, address, name, observed)
    product_execute.Product._native = native_edge
    measure(importlib.import_module('image_loader').Image, 'load')
    measure(json, 'dumps')
    measure(Path, 'write_text')
    measure(backend.PythonBackend, "call")
    profiler = cProfile.Profile() if args.profile else None
    output = io.StringIO()
    status = 0
    start = time.perf_counter()
    cpu_start = time.process_time()
    profile_window = []
    def profile_end(signum, frame):
        profiler.disable()
        profile_window.append(time.perf_counter()-start)
    def time_limit(signum, frame):
        for pid in forked:
            try:
                child, status = os.waitpid(pid, os.WNOHANG)
                if child == 0:
                    os.kill(pid, signal.SIGTERM)
                    os.waitpid(pid, 0)
            except (ChildProcessError, ProcessLookupError):
                pass
        raise SystemExit(124)
    try:
        sys.argv = args.entry
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            if profiler:
                profiler.enable()
                signal.signal(signal.SIGALRM, profile_end)
                signal.setitimer(signal.ITIMER_REAL, 30)
            elif args.limit_seconds:
                signal.signal(signal.SIGALRM, time_limit)
                signal.setitimer(signal.ITIMER_REAL, args.limit_seconds)
            runpy.run_path(str(ROOT / args.entry[0]), run_name="__main__")
    except SystemExit as exc:
        status = exc.code if isinstance(exc.code, int) else int(bool(exc.code))
    except Exception as exc:
        status = 99
        records.append(dict(type=type(exc).__name__, message=str(exc)[:300]))
    finally:
        if profiler:
            profiler.disable()
            signal.setitimer(signal.ITIMER_REAL, 0)
        elif args.limit_seconds:
            signal.setitimer(signal.ITIMER_REAL, 0)
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            atexit._run_exitfuncs()
    elapsed = time.perf_counter()-start
    cpu = time.process_time()-cpu_start
    builtins.open, io.open, Path.mkdir = original_open, original_io_open, original_mkdir
    Path.open = original_path_open
    accessor.open = original_accessor_open
    builtins.__import__ = original_import
    if profiler:
        profiler.dump_stats(str(folder / "profile.bin"))
    # Original text stays in memory. Report names, return codes and counts only.
    summary = dict(name=args.name, side=args.side, returncode=status, wall=elapsed,
                   cpu=cpu, stdout_lines=len(output.getvalue().splitlines()),
                   output_count=len(mapped), timings=timed, errors=records,
                   setup_wall=start-setup_start, mode=args.mode,
                   profile_window=profile_window,
                   max_rss=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    summary['runner_sha256'] = runner_sha
    summary['stdout_sha256'] = hashlib.sha256(output.getvalue().encode()).hexdigest()
    summary['children'] = child_calls
    summary['cli'] = cli_calls
    summary['entry_symbols'] = entry_symbols
    usage = resource.getrusage(resource.RUSAGE_CHILDREN)
    summary['child_cpu'] = usage.ru_utime+usage.ru_stime
    summary['fork_count'] = len(forked)
    summary['load_average'] = os.getloadavg()
    summary['logical_cpus'] = os.cpu_count()
    if args.side == 'fast':
        summary['cache'] = prefix_cache.STATS
    (folder / "summary.json").write_text(json.dumps(summary, indent=2)+"\n")
    (folder / "output_map.json").write_text(json.dumps(mapped, default=str, indent=2)+"\n")
    print(json.dumps({k:summary[k] for k in ('name', 'side', 'returncode', 'wall', 'cpu', 'child_cpu', 'output_count')}))
    if records:
        print(json.dumps(records))
    return status


if __name__ == "__main__":
    try:
        result = main()
    except Exception as error:
        print(json.dumps(dict(returncode=99, error_type=type(error).__name__)))
        result = 99
    sys.exit(result)
