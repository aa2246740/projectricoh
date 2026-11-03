# g139 copy (package from G139_PACKAGE) of research/g138_persist/legacy/users_gxui.py; originally a copy of research/review_v38_g137/users_gxui.py.
import ast
import builtins
import runpy
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
import hashlib
import os
G138_DAT = ROOT / os.environ.get('G139_PACKAGE', 'firmware/package_v38_g139') / 'local/SD_ROOT/GXRCE.DAT'
TARGET = ROOT / 'research/review_g135_gpt/users_gxui.py'
original = builtins.compile

class CurrentDat(ast.NodeTransformer):
    def visit_Constant(self, node):
        if isinstance(node.value, str):
            value = node.value.replace('firmware/package_v37_g135', os.environ.get('G139_PACKAGE', 'firmware/package_v38_g139'))
            value = value.replace('57743bc105bc3d51b7fa65b44efd90afb022b2356d4e7846d470cc0c641c438a',
                                  hashlib.sha256(G138_DAT.read_bytes()).hexdigest())
            return ast.copy_location(ast.Constant(value), node)
        if type(node.value) is int and node.value == 135:
            return ast.copy_location(ast.Constant(int.from_bytes(G138_DAT.read_bytes()[28:32], 'big')), node)
        if type(node.value) is int and node.value == 89572:
            return ast.copy_location(ast.Constant(G138_DAT.stat().st_size), node)
        return node

def current(source, filename, mode, flags=0, dont_inherit=False, optimize=-1, **kwargs):
    if str(filename) == str(TARGET):
        tree = source if isinstance(source, ast.AST) else original(source, filename, mode, ast.PyCF_ONLY_AST)
        tree = ast.fix_missing_locations(CurrentDat().visit(tree))
        if flags & ast.PyCF_ONLY_AST:
            return tree
        return original(tree, filename, mode, flags, dont_inherit, optimize, **kwargs)
    return original(source, filename, mode, flags, dont_inherit, optimize, **kwargs)

builtins.compile = current
try:
    if __name__ == '__main__':
        sys.argv[0] = str(TARGET)
        runpy.run_path(str(TARGET), run_name='__main__')
    else:
        loaded = runpy.run_path(str(TARGET), run_name='users_current')
        globals().update({key: value for key, value in loaded.items() if not key.startswith('__')})
except SystemExit:
    raise
except BaseException as exc:
    print(type(exc).__name__ + ': ' + str(exc), file=sys.stderr)
    for frame in traceback.extract_tb(exc.__traceback__):
        print(f'{frame.filename}:{frame.lineno}:{frame.name}', file=sys.stderr)
    sys.exit(1)
