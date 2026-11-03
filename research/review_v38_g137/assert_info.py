import ast
import builtins
import json
import runpy
import sys
from pathlib import Path

target = Path(sys.argv[1]).resolve()
minimum = int(sys.argv[2]) if len(sys.argv) > 2 else 150
maximum = int(sys.argv[3]) if len(sys.argv) > 3 else 180
original = builtins.compile
rows = []
def observed(source, filename, mode, flags=0, dont_inherit=False, optimize=-1, **kwargs):
    if str(filename) == str(target) and mode == 'exec':
        tree = source if isinstance(source, ast.AST) else original(source, filename, mode, ast.PyCF_ONLY_AST)
        for node in ast.walk(tree):
            if isinstance(node,ast.FunctionDef) and node.name in ('values','fork_case','scroll'):
                steps=[]
                for item in node.body:
                    calls=[v for v in ast.walk(item) if isinstance(v,ast.Call) and getattr(v.func,'id',None)=='fork_case']
                    if calls:steps.append({'line':item.lineno,'kind':type(item).__name__,
                        'calls':[[getattr(v,'value',getattr(v,'id',type(v).__name__)) for v in call.args] for call in calls]})
                rows.append({'function':node.name,'arguments':[v.arg for v in node.args.args],'steps':steps})
                if node.name=='scroll':
                    rows.append({'constructors':[{'targets':[getattr(v,'id',type(v).__name__) for v in item.targets],
                                 'call':getattr(item.value.func,'attr',getattr(item.value.func,'id','')),
                                 'module':getattr(getattr(item.value.func,'value',None),'id',''),
                                 'arguments':[getattr(v,'id',getattr(v,'value',type(v).__name__)) for v in item.value.args]}
                                for item in node.body if isinstance(item,ast.Assign) and isinstance(item.value,ast.Call)]})
            if isinstance(node,ast.Call) and minimum <= node.lineno <= maximum:
                values=[v.value for v in node.args if isinstance(v,ast.Constant)]
                rows.append({'line':node.lineno,'call':getattr(node.func,'attr',getattr(node.func,'id',type(node.func).__name__)),
                             'values':values})
            if isinstance(node, ast.Assert) and minimum <= node.lineno <= maximum:
                rows.append({'line': node.lineno, 'test_kind': type(node.test).__name__,
                    'attributes': [v.attr for v in ast.walk(node.test) if isinstance(v, ast.Attribute)],
                    'strings': [v.value for v in ast.walk(node.test) if isinstance(v, ast.Constant) and isinstance(v.value, str)],
                    'numbers': [v.value for v in ast.walk(node.test) if isinstance(v, ast.Constant) and type(v.value) is int]})
    return original(source, filename, mode, flags, dont_inherit, optimize, **kwargs)
builtins.compile = observed
sys.argv = [str(target)]
try:
    runpy.run_path(str(target), run_name='path_info')
except BaseException as exc:
    print(type(exc).__name__)
print(json.dumps(rows, indent=2, default=lambda value:type(value).__name__))
