import ast
import builtins
import runpy
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TARGET = ROOT / 'research/review_g135_gpt/users_gxui.py'
original = builtins.compile

class CurrentDat(ast.NodeTransformer):
    def visit_Constant(self, node):
        if isinstance(node.value, str):
            value = node.value.replace('firmware/package_v37_g135', 'firmware/package_v38_g137')
            value = value.replace('57743bc105bc3d51b7fa65b44efd90afb022b2356d4e7846d470cc0c641c438a',
                                  '78dcbb9a2735cd84e55385683ce0296b97818ddf90f8b492d9003512dbeff3f8')
            return ast.copy_location(ast.Constant(value), node)
        if type(node.value) is int and node.value == 135:
            return ast.copy_location(ast.Constant(137), node)
        if type(node.value) is int and node.value == 89572:
            return ast.copy_location(ast.Constant(89936), node)
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
