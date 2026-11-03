from pathlib import Path
import builtins
import ast
import ctypes
import io
import importlib.machinery
import hashlib
import json
import os
import runpy
import subprocess
import sys
import traceback
import types

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'research/review_g135_gpt'
JOB = os.environ.get('REVIEW_JOB', '')
WORKOUT = OUT / 'local/jobs' / JOB if JOB else OUT
OLD = ROOT / 'research/review_g135'
RUNNER = OLD / 'runner.py'
raw_open = builtins.open
raw_compile = builtins.compile
raw_io = io.open
raw_mkdir = Path.mkdir
raw_os_mkdir = os.mkdir
raw_stat = Path.stat
raw_process = subprocess.Popen.__init__
raw_exec_module = importlib.machinery.SourceFileLoader.exec_module
raw_library = ctypes.CDLL.__init__
USER_API = runpy.run_path(str(OUT / 'users_gxui.py'), run_name='review_user_api')
sys.tracebacklimit = 16
with raw_open(WORKOUT / 'bridge-start.json', 'w') as stream:
    json.dump({'bridge_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), 'runner_sha256': hashlib.sha256(RUNNER.read_bytes()).hexdigest(), 'args': sys.argv[1:]}, stream, indent=2)
    stream.write('\n')
for family in ['review_g124', 'review_g126']:
    folder = OLD / 'local/checks' / family / 'local/layout'
    for source in folder.glob('*.json'):
        target = WORKOUT / source.relative_to(OLD)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read_bytes())


def destination(value, writing=False):
    if isinstance(value, int):
        return value
    try:
        path = Path(os.fspath(value))
    except TypeError:
        return value
    if not path.is_absolute():
        path = ROOT / path
    try:
        rel = path.relative_to(OLD)
    except ValueError:
        return value
    target = WORKOUT / rel
    if not writing and rel.parts and rel.parts[0] == 'local' and not os.path.exists(target):
        shared = OUT / 'local/jobs/user-tool' / rel
        if not os.path.exists(shared):
            shared = Path(str(shared).replace('/checks/review_g126/', '/checks/review_g124/'))
        if os.path.exists(shared):
            return str(shared)
    if writing or (rel.parts and rel.parts[0] == 'local'):
        return str(target)
    return value


def file_open(original, value, mode='r', *args, **kwargs):
    target = destination(value, any(c in mode for c in 'wax+'))
    if target != value:
        kwargs.pop('opener', None)
    return original(target, mode, *args, **kwargs)


def mkdir(self, *args, **kwargs):
    mode = args[0] if args else kwargs.get('mode', 0o777)
    parents = args[1] if len(args) > 1 else kwargs.get('parents', False)
    exist_ok = args[2] if len(args) > 2 else kwargs.get('exist_ok', False)
    target = Path(destination(self, True))
    try:
        raw_os_mkdir(target, mode)
    except FileNotFoundError:
        if not parents:
            raise
        mkdir(target.parent, parents=True, exist_ok=True)
        raw_os_mkdir(target, mode)
    except FileExistsError:
        if not exist_ok or not target.is_dir():
            raise


def process(self, command, *args, **kwargs):
    if isinstance(command, (tuple, list)):
        command = [str(x).replace(str(OLD / 'local'), str(WORKOUT / 'local')) for x in command]
        command = [str(OUT / 'users_gxui.py') if str(x).endswith(('/user_entries.py', '/user_entries_g135.py')) else x for x in command]
    if isinstance(kwargs.get('env'), dict):
        kwargs['env'] = dict(kwargs['env'], TMPDIR=str(WORKOUT / 'local/tmp'))
    with raw_open(WORKOUT / 'local/processes.jsonl', 'a') as stream:
        stream.write(json.dumps({'argv': command, 'temporary': str(WORKOUT / 'local/tmp')}) + '\n')
    return raw_process(self, command, *args, **kwargs)


def execute_module(self, module):
    raw_exec_module(self, module)
    filename = str(getattr(module, '__file__', ''))
    if filename.endswith('/candidate/ui_data.py'):
        module.parse_dat = USER_API['parse_dat']
        module.replace_users = USER_API['replace_users']


def library(self, name, *args, **kwargs):
    return raw_library(self, destination(name), *args, **kwargs)


def compile_fields(source, filename, mode, flags=0, dont_inherit=False, optimize=-1, **kwargs):
    selected = str(filename).endswith(('/review_g124/user_acceptance.py', '/review_g126/user_acceptance.py'))
    if not selected or mode != 'exec' or flags & ast.PyCF_ONLY_AST:
        return raw_compile(source, filename, mode, flags, dont_inherit, optimize, **kwargs)
    tree = source if isinstance(source, ast.AST) else ast.parse(source, filename=str(filename))
    state_names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Attribute) and node.value.func.attr == 'state':
            state_names.update(target.id for target in node.targets if isinstance(target, ast.Name))
    bindings = []

    class Readings(ast.NodeTransformer):
        def visit_Call(self, node):
            self.generic_visit(node)
            if isinstance(node.func, ast.Attribute) and node.func.attr == 'goto' and len(node.args) == 2 and all(isinstance(value, ast.Constant) for value in node.args):
                if [value.value for value in node.args] == [1, 3]:
                    node.args[1] = ast.copy_location(ast.Constant(value=6), node.args[1])
                    bindings.append({'line': node.lineno, 'field': 'Default.row', 'before': 3, 'after': 6})
            return node

        def visit_Compare(self, node):
            self.generic_visit(node)
            if len(node.ops) == 1 and isinstance(node.ops[0], ast.Eq) and len(node.comparators) == 1 and isinstance(node.comparators[0], ast.Constant) and node.comparators[0].value == '<FCC-001':
                bindings.append({'line': node.lineno, 'field': 'user.card.title', 'before': 'stop at the display difference', 'after': 'record, continue, retain the group failure'})
                return ast.copy_location(ast.Call(func=ast.Name(id='review_compare_title', ctx=ast.Load()), args=[node.left, node.comparators[0]], keywords=[]), node)
            left = node.left
            if not isinstance(left, ast.Subscript) or not isinstance(left.slice, ast.Constant) or left.slice.value != 'levels':
                return node
            owner = left.value
            state = isinstance(owner, ast.Name) and owner.id in state_names
            state = state or (isinstance(owner, ast.Call) and isinstance(owner.func, ast.Attribute) and owner.func.attr == 'state')
            if not state:
                return node
            for index, expected in enumerate(node.comparators):
                if isinstance(expected, ast.Call) and isinstance(expected.func, ast.Name) and expected.func.id == 'review_expected_levels':
                    continue
                node.comparators[index] = ast.copy_location(ast.Call(func=ast.Name(id='review_expected_levels', ctx=ast.Load()), args=[expected], keywords=[]), expected)
                bindings.append({'line': node.lineno, 'field': 'state.levels', 'before': 'GXUI v1 eleven-byte expectation', 'after': 'ten int16 controls with Amount 100'})
            return node

    tree = Readings().visit(tree)
    if bindings:
        assert sum(value['field'] == 'state.levels' for value in bindings) == 4
        assert sum(value['field'] == 'Default.row' for value in bindings) == 1
        position = 1 if tree.body and isinstance(tree.body[0], ast.Expr) and isinstance(tree.body[0].value, ast.Constant) and isinstance(tree.body[0].value.value, str) else 0
        while position < len(tree.body) and isinstance(tree.body[position], ast.ImportFrom) and tree.body[position].module == '__future__':
            position += 1
        tree.body.insert(position, ast.ImportFrom(module='user_readings', names=[ast.alias(name='expected_levels', asname='review_expected_levels'), ast.alias(name='compare_title', asname='review_compare_title'), ast.alias(name='finish_user_checks', asname='review_finish_user_checks')], level=0))
        tree.body.append(ast.Expr(value=ast.Call(func=ast.Name(id='review_finish_user_checks', ctx=ast.Load()), args=[], keywords=[])))
        ast.fix_missing_locations(tree)
        with raw_open(WORKOUT / 'local/user-read-bindings.json', 'w') as stream:
            json.dump({'script': str(filename), 'bindings': bindings, 'assertions_removed': 0}, stream, indent=2)
            stream.write('\n')
    return raw_compile(tree, filename, mode, flags, dont_inherit, optimize, **kwargs)


def plain_exception(kind, error, trace, limit=None, file=None, chain=True):
    stream = file if file is not None else sys.stderr
    stream.write(getattr(kind, '__name__', type(error).__name__) + ': ' + str(error) + '\n')
    count = 0
    while trace and (limit is None or count < limit):
        frame = trace.tb_frame
        stream.write(frame.f_code.co_filename + ':' + str(trace.tb_lineno) + ':' + frame.f_code.co_name + '\n')
        trace = trace.tb_next
        count += 1


def format_exception(kind, error, trace, limit=None, chain=True):
    stream = io.StringIO()
    plain_exception(kind, error, trace, limit, stream, chain)
    return stream.getvalue().splitlines(True)


def fields(frame, event, arg):
    if frame.f_code.co_filename == str(RUNNER):
        values = frame.f_globals
        handler = values.get('unhandled')
        if callable(handler) and not values.get('review_error_handler_ready'):
            def observed_error(kind, error, trace):
                current_trace = trace
                while current_trace:
                    current_frame = current_trace.tb_frame
                    filename = current_frame.f_code.co_filename
                    if filename.endswith('/user_acceptance.py'):
                        record = {'file': filename, 'line': current_trace.tb_lineno, 'states': []}
                        for name, value in list(current_frame.f_locals.items()):
                            if callable(getattr(value, 'state', None)) and hasattr(value, 'p'):
                                try:
                                    state = value.state()
                                    detail = {'name': name, 'state': {key: state[key] for key in ['screen', 'cur', 'top', 'count', 'physical', 'slot', 'levels', 'applied_user', 'labels'] if key in state}}
                                    if isinstance(getattr(value, 'dat', None), (bytes, bytearray)):
                                        detail['dat_sha256'] = hashlib.sha256(value.dat).hexdigest()
                                    record['states'].append(detail)
                                except BaseException as state_error:
                                    record['states'].append({'name': name, 'error': type(state_error).__name__})
                        with raw_open(WORKOUT / 'local/user-observation.json', 'w') as stream:
                            json.dump(record, stream, indent=2)
                            stream.write('\n')
                    current_trace = current_trace.tb_next
                return handler(kind, error, trace)
            values['unhandled'] = observed_error
            values['review_error_handler_ready'] = True
        if isinstance(values.get('temporary'), Path):
            values['temporary'] = WORKOUT / 'local/tmp'
    return fields


def scoped_guard(event, arguments):
    if arguments and isinstance(arguments[0], (str, bytes)):
        value = arguments[0]
        if isinstance(value, bytes):
            value = value.decode(errors='replace')
        if value == review_output_path or value.startswith(review_output_path + '/'):
            return
    return review_prior_guard(event, arguments)


def relocate_guards(event, arguments):
    if event not in ('os.mkdir', 'open', 'sys.addaudithook'):
        return
    spaces = [vars(module) for module in list(sys.modules.values()) if isinstance(module, types.ModuleType)]
    frame = sys._getframe(1)
    while frame:
        spaces.append(frame.f_globals)
        frame = frame.f_back
    for space in spaces:
        function = space.get('fence')
        if not isinstance(function, types.FunctionType):
            continue
        namespace = function.__globals__
        if namespace.get('review_guard_ready'):
            continue
        namespace['review_prior_guard'] = types.FunctionType(function.__code__, namespace, function.__name__, function.__defaults__, function.__closure__)
        namespace['review_output_path'] = str(OUT)
        namespace['review_guard_ready'] = True
        function.__code__ = scoped_guard.__code__


builtins.open = lambda value, mode='r', *a, **k: file_open(raw_open, value, mode, *a, **k)
builtins.compile = compile_fields
traceback.print_exception = plain_exception
traceback.format_exception = format_exception
sys.excepthook = lambda kind, error, trace: plain_exception(kind, error, trace)
io.open = lambda value, mode='r', *a, **k: file_open(raw_io, value, mode, *a, **k)
Path.mkdir = mkdir
Path.stat = lambda self, *a, **k: raw_stat(Path(destination(self)), *a, **k)
subprocess.Popen.__init__ = process
importlib.machinery.SourceFileLoader.exec_module = execute_module
ctypes.CDLL.__init__ = library
sys.addaudithook(relocate_guards)
if len(sys.argv) >= 3 and sys.argv[1] == '--standalone':
    script = (ROOT / sys.argv[2]).resolve()
    assert script in [OLD / 'accept_rerun.py', OLD / 'accept_parts.py']
    sys.argv = [str(script)] + sys.argv[3:]
    sys.path.insert(0, str(OLD))
    runpy.run_path(str(script), run_name='__main__')
    raise SystemExit(0)
if sys.argv[1:] == ['--reference-proof']:
    reference = runpy.run_path(str(OLD / 'r2_oracle.py'), run_name='reference_paths')
    Reference = reference['reference_class'](OLD / 'local/checks/review_g126')
    closure = dict(zip(Reference.compute.__code__.co_freevars, [cell.cell_contents for cell in Reference.compute.__closure__]))
    stock, base = next(iter(closure['identities']))
    item = Reference()
    item.unit = '50mm'
    item.slot = 1
    result = bytes(item.compute(base, stock, [100] + [0] * 9))
    assert result == base
    summary = {'status': 'PASS', 'bytes_compared': 552, 'default_equal_base': True, 'base_sha256': hashlib.sha256(base).hexdigest(), 'observed_sha256': hashlib.sha256(result).hexdigest()}
    (OUT / 'evidence/reference-paths.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps(summary), flush=True)
    raise SystemExit(0)
sys.argv = [str(RUNNER)] + sys.argv[1:]
sys.path.insert(0, str(OLD))
sys.path.insert(0, str(OUT))
import user_readings
user_readings.configure(WORKOUT / 'local/user-display.json', raw_open)
sys.settrace(fields)
try:
    runpy.run_path(str(RUNNER), run_name='__main__')
except SystemExit:
    raise
except BaseException as error:
    os.write(2, (type(error).__name__ + ' ' + str(error)[:400] + '\n').encode())
    trace = error.__traceback__
    while trace:
        frame = trace.tb_frame
        os.write(2, (Path(frame.f_code.co_filename).name + ':' + str(trace.tb_lineno) + ':' + frame.f_code.co_name + '\n').encode())
        trace = trace.tb_next
    raise SystemExit(1)
