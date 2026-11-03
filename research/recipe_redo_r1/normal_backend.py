"""Optional task-local fast backend; refuses use before an explicit switch receipt."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import runtime as rt
import ast
import os
import types
import hashlib
import json

ALIASES = {'runtime': 'recipe_gn_runtime', 'native': 'recipe_gn_native',
           'exact_table': 'recipe_gn_exact_table',
           'solver': 'recipe_gn_solver', 'lagged': 'recipe_gn_lagged',
           'parameterization': 'recipe_gn_parameterization'}


def relocated_module(name, path):
    """Relocate imports in memory; frozen source bytes remain unchanged."""
    tree = ast.parse(path.read_text(), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for item in node.names:
                if item.name in ALIASES:
                    previous = item.name
                    item.name = ALIASES[previous]
                    item.asname = item.asname or previous
        if isinstance(node, ast.ImportFrom) and node.module in ALIASES:
            node.module = ALIASES[node.module]
    ast.fix_missing_locations(tree)
    module = types.ModuleType(name)
    module.__file__ = str(path)
    sys.modules[name] = module
    exec(compile(tree, str(path), 'exec'), module.__dict__)
    return module


def load():
    if hasattr(load, 'cached'):
        return load.cached
    authorization_path = rt.LOCAL/'guarded_normal_switch_authorization.json'
    if not authorization_path.is_file():
        raise RuntimeError('Waiting for fit-fast-r1 equivalence and an explicit switch notice')
    authorization = rt.read(authorization_path)
    assert authorization['switch_notice'] and authorization['equivalence_passed'] is True
    assert authorization['source_files'], 'Delivered engine source hashes are required'
    assert authorization.get('solver') in ('guarded_normal',)
    root = rt.LOCAL/'guarded_normal_source/tools/fit_fast'
    copied = {}
    for relative, expected in authorization['source_files'].items():
        original = (rt.ROOT/'tools/fit_fast'/relative).resolve()
        assert original.is_relative_to(rt.ROOT/'tools/fit_fast')
        destination = root/relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.exists():
            assert rt.sha(original) == expected, 'Delivered fast-engine source changed before freezing'
            destination.write_bytes(original.read_bytes())
        assert rt.sha(destination) == expected
        copied[relative] = expected
    for name in ('engine.py', 'native.py', 'solver.py', 'kernels.c'):
        assert name in copied, 'Incomplete engine delivery'
    reference = rt.ROOT/'tools/fit_fast/reference/research/look_ceiling_r1/ceiling_model.py'
    assert rt.sha(reference) == rt.sha(rt.SOURCE/'research/look_ceiling_r1/ceiling_model.py'), 'Reference model differs'
    adapter = types.ModuleType('recipe_gn_runtime')
    adapter.__dict__.update(rt.__dict__)
    adapter.__name__ = 'recipe_gn_runtime'
    adapter.HERE, adapter.PRIVATE, adapter.REFERENCE = root, rt.LOCAL/'normal_fast_engine', rt.SOURCE
    adapter.ref_module = lambda name, filename: rt.module(name, rt.SOURCE/'research/look_ceiling_r1'/filename)
    sys.modules['recipe_gn_runtime'] = adapter
    os.environ['FIT_FAST_NATIVE'] = 'c'
    os.environ['FIT_FAST_SOLVER'] = authorization['solver']
    os.environ['FIT_FAST_GUARD_FACTOR'] = 'normal'
    os.environ.pop('FIT_FAST_RCOND_FLOOR',None)
    native = relocated_module('recipe_gn_native', root/'native.py')
    relocated_module('recipe_gn_exact_table', root/'exact_table.py')
    solver = relocated_module('recipe_gn_solver', root/'solver.py')
    engine = relocated_module('recipe_gn_engine', root/'engine.py')
    # Build once in the first worker, before any later multi-process sweep.
    native.library()
    adapter_files = {name: rt.sha(rt.HERE/name) for name in
        ('normal_backend.py', 'fast_equivalence.py', 'runtime.py', 'fit_one.py', 'guarded_problem.py', 'entry_codec.py', 'capabilities.py')}
    fingerprint = hashlib.sha256(json.dumps(dict(source_files=copied,
        solver=authorization['solver'], adapter_files=adapter_files), sort_keys=True).encode()).hexdigest()
    adapter_receipt = dict(created_utc=rt.utc(),
        switch_authorization_sha256=rt.sha(authorization_path), source_files=copied,
        backend_fingerprint=fingerprint, adapter_files=adapter_files,
        solver=authorization['solver'], output_root=str(adapter.PRIVATE),
        archived_studio_used=True, no_upstream_writes=True, imported_original_runtime=False,
        task_equivalence_gate='separate equivalence_task.json must match backend_fingerprint')
    receipt_path = rt.LOCAL/'normal_fast_engine/adapter_receipt.json'
    if not receipt_path.exists() or rt.read(receipt_path)['backend_fingerprint'] != fingerprint:
        # The mandatory single-process warm-up/equivalence step creates this
        # shared receipt. Subsequent qualified workers only read it.
        rt.dump(receipt_path, adapter_receipt)
    load.cached = engine, solver
    return load.cached
