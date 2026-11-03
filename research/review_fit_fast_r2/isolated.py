"""Review-only I/O relocation. Numerical source is loaded from the reviewed tree.

Use -I -B. Every Python write is confined to this review directory; private
arrays, dependency snapshots, compiler outputs, and solver traces go in artifacts/.
No production module is imported before the write/network/device audit is active.
"""
import ast
import hashlib
import json
import os
from pathlib import Path
import signal
import sys
import types

sys.dont_write_bytecode = True
REVIEW = Path(__file__).resolve().parent
ROOT = REVIEW.parents[1]
TOOLS = ROOT / "tools/fit_fast"
ARTIFACTS = REVIEW / "artifacts"
for key in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "VECLIB_MAXIMUM_THREADS",
            "MKL_NUM_THREADS", "NUMBA_NUM_THREADS", "BLIS_NUM_THREADS"):
    os.environ[key] = "1"
os.environ["GIT_OPTIONAL_LOCKS"] = "0"
if os.getpriority(os.PRIO_PROCESS, 0) < 15:
    os.nice(15 - os.getpriority(os.PRIO_PROCESS, 0))


def fence(event, args):
    if event in ("socket.connect", "socket.bind", "socket.getaddrinfo"):
        raise PermissionError("Review forbids network")
    if event == "open" and isinstance(args[0], (str, bytes, Path)):
        path = Path(os.fsdecode(args[0])).absolute().resolve()
        if path.is_relative_to(ROOT / "studio"):
            raise PermissionError("Review forbids studio access")
        if str(path).startswith("/dev/") and str(path) not in ("/dev/null", "/dev/urandom", "/dev/random"):
            raise PermissionError("Review forbids device access")
        mode, flags = args[1:3]
        write = isinstance(mode, str) and any(c in mode for c in "wax+")
        write |= isinstance(flags, int) and bool(flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC))
        if write and not path.is_relative_to(REVIEW):
            raise PermissionError("Review write outside its directory: " + str(path))
    if event in ("os.mkdir", "os.remove", "os.rmdir", "os.rename", "os.symlink", "os.link", "os.chmod", "os.utime"):
        for item in args[:2] if event in ("os.rename", "os.symlink", "os.link") else args[:1]:
            if isinstance(item, (str, bytes, Path)):
                path = Path(os.fsdecode(item)).absolute().resolve()
                if not path.is_relative_to(REVIEW):
                    raise PermissionError("Review mutation outside its directory: " + str(path))


sys.addaudithook(fence)
ARTIFACTS.mkdir(exist_ok=True)
# All review numerical entrypoints share two OS-released slots. The standard
# library parallel coordinator never takes a slot itself.
import fcntl
_compute_slot = None
for _slot_number in range(2):
    _candidate = (ARTIFACTS / ("compute-slot-"+str(_slot_number)+".lock")).open("a+b")
    try:
        fcntl.flock(_candidate, fcntl.LOCK_EX | fcntl.LOCK_NB)
        _compute_slot = _candidate
        break
    except BlockingIOError:
        _candidate.close()
if _compute_slot is None:
    _compute_slot = (ARTIFACTS / "compute-slot-0.lock").open("a+b")
    signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(TimeoutError("Review computation-slot deadline")))
    signal.alarm(1200)
    fcntl.flock(_compute_slot, fcntl.LOCK_EX)
sys.path.insert(0, str(TOOLS))
path = TOOLS / "runtime.py"
tree = ast.parse(path.read_text(), filename=str(path))
relocations = {
    "PRIVATE": ARTIFACTS,
    "LOCAL": ARTIFACTS / os.environ.get("REVIEW_RUN", "evaluation"),
    "SCRATCH": ARTIFACTS / "scratch",
    "REPORT": REVIEW,
    "archive": ROOT / "artifacts/downloads/fit-fast-r1/frozen_inputs/studio_source_snapshot.tar.gz",
}
changed = set()
for node in tree.body:
    if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
        key = node.targets[0].id
        if key in relocations:
            node.value = ast.parse("Path(" + repr(str(relocations[key])) + ")", mode="eval").body
            changed.add(key)
    if isinstance(node, ast.FunctionDef) and node.name in ("private_path", "allowed_write"):
        base = ARTIFACTS if node.name == "private_path" else REVIEW
        node.body = ast.parse("return Path(path).resolve().is_relative_to(Path(" + repr(str(base)) + "))").body
        changed.add(node.name)
assert changed == set(relocations) | {"private_path", "allowed_write"}, changed
ast.fix_missing_locations(tree)
rt = types.ModuleType("runtime")
rt.__file__ = str(path)
sys.modules["runtime"] = rt
exec(compile(tree, str(path), "exec"), rt.__dict__)
signal.alarm(int(os.environ.get("REVIEW_TIMEOUT", "1700")))
import atexit


def _input_receipt():
    rt.dump(ARTIFACTS / "input_receipts" / (str(os.getpid())+".json"), rt.INPUTS)


atexit.register(_input_receipt)


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write(name, value):
    rt.dump(ARTIFACTS / name, value)


def gate_module():
    sys.path.insert(0, str(TOOLS / "round2"))
    import quality_gate
    return quality_gate


if __name__ == "__main__":
    if sys.argv[1] == "gate":
        policy = REVIEW / "round2/policy.json"
        policy.parent.mkdir(exist_ok=True)
        if not policy.exists():
            policy.write_bytes((ROOT / "research/fit_fast_r1/round2/policy.json").read_bytes())
        gate = gate_module()
        private = ROOT / "artifacts/downloads/fit-fast-r1"
        gate.DEFAULT_REFS = [private / "bench" / tag / "r0-reference" for tag in
            ("full-ref-a-final", "full-ref-b2", "full-ref-c", "full-ref-d")]
        sys.argv = [str(TOOLS / "round2/quality_gate.py"), *sys.argv[2:]]
        gate.main()
    elif sys.argv[1] == "smoke":
        import engine
        c = rt.camera_for_unit(2)
        rt.np.asarray(c.row.coef)
        import native
        native.library()
        print(json.dumps(dict(ok=True, nice=os.getpriority(os.PRIO_PROCESS, 0),
                              review=str(REVIEW), runtime_source_sha256=sha(path))))
    elif sys.argv[1] == "fit":
        import argparse
        import run
        parser = argparse.ArgumentParser()
        parser.add_argument("--indices", required=True)
        parser.add_argument("--phase", choices=("base", "full"), required=True)
        parser.add_argument("--nfev", type=int, default=100)
        options = parser.parse_args(sys.argv[2:])
        options.engine = "fast"
        options.solver = "guarded_normal"
        options.full_fields = options.phase == "full"
        options.physical_asym = False
        options.observed_study_processes = []
        os.environ["FIT_FAST_SOLVER"] = "guarded_normal"
        os.environ["FIT_FAST_GUARD_FACTOR"] = "normal"
        os.environ.pop("FIT_FAST_RCOND_FLOOR", None)
        rest = ["--indices", options.indices, "--nfev", str(options.nfev)]
        rest += ["--full-fields"] if options.full_fields else ["--keys", "L0,L1"]
        run.worker(rest, options)
    else:
        raise SystemExit("Use gate, fit, or smoke")
