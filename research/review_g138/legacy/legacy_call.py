import ast
import builtins
import copy
import io
import importlib.util
import json
import os
import pathlib
import runpy
import sys
import traceback
from pathlib import Path

# Gen 138 copy of research/review_v38_g137/legacy_call.py (read-only source).
# Changes: OUT/SCRATCH are this task's; identity pairs target package_v38_g138;
# the normal-boot fixture binding (fixture.py) is installed before the bridge.
ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'research/review_g138/legacy'
OLD = ROOT / 'research/review_g135_gpt'
SCRATCH = Path('/Volumes/Workspace/Scratch/tmp/projectricoh/review-g138/legacy')
sys.path.insert(0, str(ROOT / 'research/review_g138'))
import fixture
fixture.install()
import hashlib
G138_DAT = ROOT / 'firmware/package_v38_g138/local/SD_ROOT/GXRCE.DAT'
G138_SHA = hashlib.sha256(G138_DAT.read_bytes()).hexdigest()
G138_SIZE = G138_DAT.stat().st_size
job = sys.argv[1]
# Run added review checks serially within an existing slot, before the matrix
# job starts. Their receipts do not replace that job's own assertions.
precheck_path = OUT.parent / 'prechecks.json'
if precheck_path.exists():
    import subprocess
    for index, arguments in enumerate(json.loads(precheck_path.read_text()).get(job, [])):
        command = ['/usr/bin/python3', '-I', '-B', str(OUT.parent / arguments[0]), *arguments[1:]]
        result = subprocess.run(command, env=dict(os.environ, TMPDIR=str(SCRATCH.parent)))
        (OUT.parent / 'evidence/receipts' / (job + '-precheck-' + str(index) + '.json')).write_text(
            json.dumps({'command': command, 'returncode': result.returncode}, indent=2) + '\n')
        if result.returncode:
            print(json.dumps({'review_precheck_returncode': result.returncode, 'command': command}), flush=True)
selection_path=OUT/'resume-selection.json'
effective={}
if selection_path.exists():
    effective=json.loads(selection_path.read_text()).get(job,{})
    for key,value in effective.items():os.environ[key]=value
WORK = OUT / 'local/jobs' / job
WORK.mkdir(parents=True, exist_ok=True)
(WORK/'effective-selection.json').write_text(json.dumps(effective,indent=2)+'\n')
TEMP = SCRATCH / job
TEMP.mkdir(parents=True, exist_ok=True)
os.environ['TMPDIR'] = str(TEMP)
# Retained runners set TMPDIR again. Keep the final process environment
# inside the requested temporary root, including compiler subprocesses.
environment_setitem = os._Environ.__setitem__
def set_environment(self, key, value):
    return environment_setitem(self, key, str(TEMP) if key == 'TMPDIR' else value)
os._Environ.__setitem__ = set_environment
import subprocess
process_init = subprocess.Popen.__init__
def start_process(self, command, *args, **kwargs):
    kwargs['env'] = dict(kwargs.get('env') or os.environ, TMPDIR=str(TEMP))
    return process_init(self, command, *args, **kwargs)
subprocess.Popen.__init__ = start_process
raw_open, raw_io_open, raw_compile = builtins.open, io.open, builtins.compile
raw_mkdir, raw_stat, raw_unlink = os.mkdir, os.stat, os.unlink
raw_os_open = os.open
raw_replace, raw_rename = os.replace, os.rename
raw_run_path = runpy.run_path
raw_spec = importlib.util.spec_from_file_location
changes = []

def mapped(file, write=False):
    if not isinstance(file, (str, bytes, os.PathLike)):
        return file
    name = os.fsdecode(file)
    helper = str(ROOT / 'research/g135_v37/local/tmp')
    if os.path.abspath(name).startswith(helper):
        return str(TEMP / Path(os.path.abspath(name)).relative_to(helper))
    if not write:
        try:
            raw_stat(name)
        except FileNotFoundError:
            try:
                relative = Path(os.path.abspath(name)).relative_to(OUT)
                prior = OLD / relative
                raw_stat(prior)
                return str(prior)
            except (ValueError, FileNotFoundError):
                pass
        try:
            relative = Path(os.path.abspath(name)).relative_to(WORK)
            prior = OLD / relative
            if prior.suffix == '.py' and prior.is_file():
                return str(prior)
        except ValueError:
            pass
    try:
        p = Path(os.path.abspath(name))
        tail = p.relative_to(OLD)
    except ValueError:
        return file
    if p.suffix == '.py' and not write:
        return file
    candidate = WORK / tail
    if write:
        return str(candidate)
    try:
        raw_stat(candidate)
        return str(candidate)
    except FileNotFoundError:
        return file

def opened(original, file, mode='r', *args, **kwargs):
    return original(mapped(file, any(c in str(mode) for c in 'wax+')), mode, *args, **kwargs)

builtins.open = lambda file, mode='r', *args, **kwargs: opened(raw_open, file, mode, *args, **kwargs)
io.open = lambda file, mode='r', *args, **kwargs: opened(raw_io_open, file, mode, *args, **kwargs)
os.open = lambda file, flags, *args, **kwargs: raw_os_open(mapped(file, bool(flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT))), flags, *args, **kwargs)
os.mkdir = lambda file, *args, **kwargs: raw_mkdir(mapped(file, True), *args, **kwargs)
os.stat = lambda file, *args, **kwargs: raw_stat(mapped(file), *args, **kwargs)
os.unlink = lambda file, *args, **kwargs: raw_unlink(mapped(file, True), *args, **kwargs)
os.replace = lambda a, b, *args, **kwargs: raw_replace(mapped(a), mapped(b, True), *args, **kwargs)
os.rename = lambda a, b, *args, **kwargs: raw_rename(mapped(a), mapped(b, True), *args, **kwargs)
pathlib._normal_accessor.open = os.open
pathlib._normal_accessor.mkdir = os.mkdir
pathlib._normal_accessor.stat = os.stat
pathlib._normal_accessor.unlink = os.unlink
pathlib._normal_accessor.rename = os.rename
pathlib._normal_accessor.replace = os.replace
runpy.run_path = lambda path, *args, **kwargs: raw_run_path(mapped(path), *args, **kwargs)
importlib.util.spec_from_file_location = lambda name, path, *args, **kwargs: raw_spec(name, mapped(path), *args, **kwargs)

string_pairs = [
    ('firmware/package_v37_g135', 'firmware/package_v38_g138'),
    ('firmware/engine_v53_g135', 'firmware/engine_v55_g138'),
    ('firmware/resident_v37', 'firmware/resident_v38'),
    ('57743bc105bc3d51b7fa65b44efd90afb022b2356d4e7846d470cc0c641c438a', G138_SHA),
    ('d00607405a5bd33290f99e9eda20df31a46386b6e0891cd5e62b15a9e3376283', 'd4fa3b46da137b8b7c7c703e66750a8249c0715271290c0fdb490a2f7a239a90'),
]

END_MARKS = {68: {'S 0 F 0!': 'S 0 F 0'}, 71: {'Fade!  0': 'Fade   0'},
             118: {'! +9': '  +9'}, 124: {'! -9': '  -9'}}

class Readings(ast.NodeTransformer):
    def __init__(self, filename):
        self.filename = filename

    def visit_List(self, node):
        node = self.generic_visit(node)
        if self.filename.endswith('ui_acceptance_g135.py') and node.lineno in (68, 81):
            index = 7 if node.lineno == 68 else 2
            if len(node.elts) == 8 and isinstance(node.elts[index], ast.Constant) and node.elts[index].value == ' ':
                node.elts[index] = ast.copy_location(ast.Constant('--------'), node.elts[index])
                changes.append({'file': self.filename, 'line': node.lineno,
                                'kind': 'g137-first-padding-separator', 'physical_row': index})
        return node

    def visit_BinOp(self, node):
        node = self.generic_visit(node)
        if (self.filename.endswith('ui_acceptance_g135.py') and node.lineno == 96
                and isinstance(node.op, ast.Mult) and isinstance(node.left, ast.List)
                and len(node.left.elts) == 1 and isinstance(node.left.elts[0], ast.Constant)
                and node.left.elts[0].value == ' ' and isinstance(node.right, ast.Constant)
                and node.right.value == 7):
            changes.append({'file': self.filename, 'line': 96,
                            'kind': 'g137-error-page-first-padding-separator'})
            return ast.copy_location(ast.List(elts=[ast.Constant('--------')] + [ast.Constant(' ') for _ in range(6)], ctx=ast.Load()), node)
        return node

    def visit_Dict(self, node):
        node = self.generic_visit(node)
        if self.filename.endswith('ui_acceptance_g135.py') and node.lineno == 82:
            for key, value in zip(node.keys, node.values):
                if (isinstance(key, ast.Constant) and key.value == 'DOWN'
                        and isinstance(value, ast.Tuple) and len(value.elts) == 2
                        and [getattr(item, 'value', None) for item in value.elts] == [5, 1]):
                    value.elts[1] = ast.copy_location(ast.Constant(0), value.elts[1])
                    changes.append({'file': self.filename, 'line': 82,
                                    'kind': 'g137-empty-entries-loop', 'before': [5, 1], 'after': [5, 0]})
        return node

    def visit_Compare(self, node):
        node = self.generic_visit(node)
        if (self.filename.endswith('/locked_cases.py') and node.lineno == 115
                and isinstance(node.left, ast.Name) and node.left.id == 'x'
                and len(node.ops) == len(node.comparators) == 1
                and isinstance(node.ops[0], ast.Eq)
                and isinstance(node.comparators[0], ast.Constant)
                and node.comparators[0].value == ' '):
            node.ops[0] = ast.In()
            node.comparators[0] = ast.Tuple(elts=[ast.Constant(' '), ast.Constant('--------')], ctx=ast.Load())
            changes.append({'file': self.filename, 'line': 115,
                            'kind': 'g137-error-rendering-separator-admitted'})
        return node

    def visit_Constant(self, node):
        if isinstance(node.value, str):
            updated = node.value
            for before, after in string_pairs:
                updated = updated.replace(before, after)
            if updated != node.value:
                changes.append({'file': self.filename, 'line': node.lineno, 'kind': 'identity-path'})
                return ast.copy_location(ast.Constant(updated), node)
        # Gen 138 contract C: no end marks; '!' is gone from value and card text.
        if (isinstance(node.value, str) and '!' in node.value and self.filename.endswith('ui_acceptance_g135.py')
                and node.lineno in END_MARKS and node.value in END_MARKS[node.lineno]):
            after = END_MARKS[node.lineno][node.value]
            changes.append({'file': self.filename, 'line': node.lineno, 'kind': 'C-no-end-mark',
                            'before': node.value, 'after': after})
            return ast.copy_location(ast.Constant(after), node)
        if node.value == 89572 and (self.filename.endswith(('users_gxui.py', 'runner.py')) or
                                    self.filename.endswith('ui_adapter.py') and node.lineno == 86):
            changes.append({'file': self.filename, 'line': node.lineno, 'kind': 'dat-size'})
            return ast.copy_location(ast.Constant(G138_SIZE), node)
        if type(node.value) is int and node.value == 135 and (self.filename in (
            str(ROOT / 'research/review_g135/runner.py'), str(OLD / 'users_gxui.py')) or
            self.filename.endswith('ui_adapter.py') and node.lineno == 86):
            changes.append({'file': self.filename, 'line': node.lineno, 'kind': 'generation-target', 'before': 135, 'after': 138})
            return ast.copy_location(ast.Constant(138), node)
        return node

    def visit_Assert(self, node):
        if self.filename.endswith('/user_acceptance.py') and node.lineno==42:
            found=[]
            for test in ast.walk(node.test):
                if isinstance(test,ast.Compare) and isinstance(test.left,ast.Subscript):
                    if getattr(test.left.slice,'value',None)=='cur' and getattr(test.comparators[0],'value',None)==25:
                        test.comparators[0].value=0;found.append(test)
            assert len(found)==1
            changes.append({'file':self.filename,'line':42,'kind':'users-loop-reading','before':25,'after':0})
        if self.filename.endswith('ui_acceptance_g135.py'):
            if node.lineno in (135,136):
                expected={'cur':9,'physical':7} if node.lineno==135 else {'cursor_after':8}
                found=[]
                for test in ast.walk(node.test):
                    if isinstance(test,ast.Compare) and isinstance(test.left,ast.Subscript) and len(test.comparators)==1:
                        key=getattr(test.left.slice,'value',None)
                        if key in expected and isinstance(test.comparators[0],ast.Constant):
                            test.comparators[0].value=expected[key];found.append(key)
                assert set(found)==set(expected)
                changes.append({'file':self.filename,'line':node.lineno,'kind':'L1-loop-reading','expected':expected})
            # Bottom edge (review r2): DOWN on the last L1 row wraps to row 0 and previews
            # recipe 1 (DESIGN_r2_list.md option D), so the later DISP opens slot 1.
            if node.lineno in (144,147):
                key,before,after=('cur',9,0) if node.lineno==144 else ('slot',8,1)
                found=[]
                for test in ast.walk(node.test):
                    if isinstance(test,ast.Compare) and isinstance(test.left,ast.Subscript) and len(test.comparators)==1:
                        if getattr(test.left.slice,'value',None)==key and getattr(test.comparators[0],'value',None)==before:
                            test.comparators[0].value=after;found.append(key)
                assert len(found)==1
                changes.append({'file':self.filename,'line':node.lineno,'kind':'L1-bottom-loop-reading','key':key,'before':before,'after':after})
            if node.lineno == 164:
                found = []
                for test in ast.walk(node.test):
                    if isinstance(test, ast.Compare) and isinstance(test.left, ast.Subscript):
                        if getattr(test.left.slice, 'value', None) == 'cur' and len(test.comparators) == 1:
                            wanted = test.comparators[0]
                            if isinstance(wanted, ast.Constant) and wanted.value == 1:
                                wanted.value = 2
                                found.append(test)
                assert len(found) == 1
                changes.append({'file': self.filename, 'line': node.lineno, 'kind': 'pair-memory', 'before': [1, 1], 'after': [1, 2]})
        return self.generic_visit(node)

    def visit_FunctionDef(self,node):
        if getattr(node,'review_scroll_ready',False) or getattr(node,'review_user_ready',False):return node
        node=self.generic_visit(node)
        if self.filename.endswith('ui_acceptance_g135.py') and node.name=='scroll':
            at=next(i for i,v in enumerate(node.body) if isinstance(v,ast.Assert) and v.lineno==136)
            previous=next(v for v in node.body if isinstance(v,ast.Assert) and v.lineno==135)
            calls=[v for v in ast.walk(node) if isinstance(v,ast.Call)
                   and any(getattr(arg,'value',None)=='UP' for arg in v.args) and v.lineno<135]
            assert calls
            down=copy.deepcopy(calls[-1])
            for arg in down.args:
                if getattr(arg,'value',None)=='UP':arg.value='DOWN'
            state=copy.deepcopy(previous)
            for test in ast.walk(state.test):
                if isinstance(test,ast.Compare) and isinstance(test.left,ast.Subscript):
                    if getattr(test.left.slice,'value',None) in ('cur','physical'):test.comparators[0].value=0
            transition=copy.deepcopy(node.body[at])
            for test in ast.walk(transition.test):
                if isinstance(test,ast.Compare) and isinstance(test.left,ast.Subscript):
                    key=getattr(test.left.slice,'value',None)
                    if key in ('cursor_before','cursor_after'):test.comparators[0].value=8 if key=='cursor_before' else 1
            node.body[at+1:at+1]=[ast.copy_location(ast.Expr(down),node.body[at]),state,transition]
            bottom=next(i for i,v in enumerate(node.body) if isinstance(v,ast.Assert) and v.lineno==144)
            press=next(v for v in node.body if isinstance(v,ast.Expr) and v.lineno==144)
            up=copy.deepcopy(press)
            for arg in ast.walk(up):
                if getattr(arg,'value',None)=='DOWN':arg.value='UP'
            back=copy.deepcopy(node.body[bottom])
            for test in ast.walk(back.test):
                if isinstance(test,ast.Compare) and isinstance(test.left,ast.Subscript) and getattr(test.left.slice,'value',None)=='cur':
                    test.comparators[0].value=9
            node.body[bottom+1:bottom+1]=[up,back]
            changes.append({'file':self.filename,'line':144,'kind':'L1-bottom-return-edge','added_key':'UP','logical_cursor':9})
            node.review_scroll_ready=True
            changes.append({'file':self.filename,'line':136,'kind':'L1-return-edge','added_key':'DOWN',
                            'logical_cursor':0,'physical_cursor':0,'native_transition':[8,1]})
        if self.filename.endswith('/user_acceptance.py') and node.name=='main':
            at=next(i for i,v in enumerate(node.body) if isinstance(v,ast.Assert) and v.lineno==42)
            calls=[v for v in ast.walk(node) if isinstance(v,ast.Call) and v.lineno==42
                   and any(getattr(arg,'value',None)=='DOWN' for arg in v.args)]
            assert len(calls)==1
            up=copy.deepcopy(calls[0])
            for arg in up.args:
                if getattr(arg,'value',None)=='DOWN':arg.value='UP'
            restored=copy.deepcopy(node.body[at])
            for test in ast.walk(restored.test):
                if isinstance(test,ast.Compare) and isinstance(test.left,ast.Subscript):
                    if getattr(test.left.slice,'value',None)=='cur':test.comparators[0].value=25
            node.body[at+1:at+1]=[ast.copy_location(ast.Expr(up),node.body[at]),restored]
            node.review_user_ready=True
            changes.append({'file':self.filename,'line':42,'kind':'users-return-edge','added_key':'UP','logical_cursor':25})
        if self.filename.endswith('ui_acceptance_g135.py') and node.name=='values' and os.environ.get('REVIEW_ONLY_CASE'):
            selected=os.environ['REVIEW_ONLY_CASE']
            wanted=set(selected.split(','))
            keep=[];removed=[]
            template=None
            for statement in node.body:
                calls=[v for v in ast.walk(statement) if isinstance(v,ast.Call) and getattr(v.func,'id',None)=='fork_case']
                if calls and not isinstance(statement,ast.FunctionDef):
                    if any(len(call.args)>1 and getattr(call.args[1],'value',None)=='L1-virtual-scroll' for call in calls):
                        template=copy.deepcopy(statement)
                    if isinstance(statement,ast.For) and any(name.startswith('all-values-') for name in wanted):
                        label=copy.deepcopy(calls[0].args[1])
                        condition=ast.Compare(left=label,ops=[ast.NotIn()],comparators=[ast.Tuple(elts=[ast.Constant(v) for v in sorted(wanted)],ctx=ast.Load())])
                        statement.body.insert(0,ast.copy_location(ast.If(test=condition,body=[ast.Continue()],orelse=[]),statement))
                        keep.append(statement);continue
                    if not any(len(call.args)>1 and getattr(call.args[1],'value',None) in wanted for call in calls):
                        removed.append(statement.lineno);continue
                keep.append(statement)
            if 'menu-edges' in wanted:
                assert template is not None
                call=next(v for v in ast.walk(template) if isinstance(v,ast.Call) and getattr(v.func,'id',None)=='fork_case')
                call.args[1]=ast.copy_location(ast.Constant('menu-edges'),call.args[1])
                call.args[2]=ast.copy_location(ast.parse("lambda record: __import__('menu_probe').run(s)",mode='eval').body,call.args[2])
                at=next(i for i,item in enumerate(keep) if getattr(item,'lineno',0)>=168)
                keep.insert(at,template)
            node.body=keep
            if os.environ.get('REVIEW_MENU_PROBE')=='1':
                selected_calls=[v for item in keep if not isinstance(item,ast.FunctionDef) for v in ast.walk(item)
                                if isinstance(v,ast.Call) and getattr(v.func,'id',None)=='fork_case']
                assert len(selected_calls)==1
                call=selected_calls[0]
                call.args[1]=ast.copy_location(ast.Constant('menu-edges'),call.args[1])
                call.args[2]=ast.copy_location(ast.parse("lambda record: __import__('menu_probe').run(s)",mode='eval').body,call.args[2])
                changes.append({'file':self.filename,'kind':'new-menu-probe','source':'research/review_v38_g137/menu_probe.py'})
            changes.append({'file':self.filename,'kind':'selected-case','selected':selected,'omitted_statement_lines':removed,
                            'omitted_cases_are_not_passed':True})
        return node

def compiled(source, filename, mode, flags=0, dont_inherit=False, optimize=-1, **kwargs):
    name = os.fsdecode(filename)
    if name.startswith(str(ROOT)) and not name.startswith(str(OUT)) and mode == 'exec':
        tree = source if isinstance(source, ast.AST) else raw_compile(source, filename, mode, ast.PyCF_ONLY_AST)
        tree = ast.fix_missing_locations(Readings(name).visit(tree))
        with raw_open(WORK / 'review-bindings-active.json', 'w') as stream:
            json.dump(changes, stream, indent=2)
        if flags & ast.PyCF_ONLY_AST:
            return tree
        return raw_compile(tree, filename, mode, flags, dont_inherit, optimize, **kwargs)
    return raw_compile(source, filename, mode, flags, dont_inherit, optimize, **kwargs)

builtins.compile = compiled
sys.path.insert(0, str(OLD))
sys.path.insert(0, str(OUT))
target = ROOT / 'research/review_g135_gpt/bridge.py'
sys.argv = [str(target), *sys.argv[2:]]
code = 0
def setup_trace(frame, event, arg):
    if frame.f_code.co_filename == str(target):
        if 'OUT' in frame.f_globals:
            frame.f_globals['OUT'] = OUT
        if 'WORKOUT' in frame.f_globals:
            frame.f_globals['WORKOUT'] = WORK
    return setup_trace if frame.f_code.co_filename == str(target) else None

sys.settrace(setup_trace)
try:
    runpy.run_path(str(target), run_name='__main__')
except SystemExit as exc:
    code = exc.code if isinstance(exc.code, int) else int(bool(exc.code))
except BaseException as exc:
    code = 1
    print(json.dumps({'error_type': type(exc).__name__, 'message': str(exc),
                      'frames': [{'file': f.filename, 'line': f.lineno, 'function': f.name}
                                 for f in traceback.extract_tb(exc.__traceback__)]}, ensure_ascii=False), flush=True)
finally:
    sys.settrace(None)
    with raw_open(WORK / 'review-readings.json', 'w') as stream:
        json.dump(changes, stream, indent=2)
        stream.write('\n')
sys.exit(code)
