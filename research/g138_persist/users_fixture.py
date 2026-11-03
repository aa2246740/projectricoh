"""Build the gen 138 user-entry fixture DAT (same 32 entries as review_g124's).

Runs research/review_g135_gpt/users_gxui.py by path with its gen 135 identity
constants rebound to the current gen 138 package (no copy, no edit). Output:
research/g138_persist/local/users-fixture/GXRCE.DAT. /usr/bin/python3 -I -B.
"""
from pathlib import Path
import ast
import builtins
import hashlib
import json
import runpy
import sys

ROOT = Path(__file__).resolve().parents[2]
TARGET = ROOT / 'research/review_g135_gpt/users_gxui.py'
DAT = ROOT / 'firmware/package_v38_g138/local/SD_ROOT/GXRCE.DAT'
OUT = Path(__file__).resolve().parent / 'local/users-fixture/GXRCE.DAT'
original = builtins.compile


def bind(dat):
    digest = hashlib.sha256(dat).hexdigest()

    class Current(ast.NodeTransformer):
        def visit_Constant(self, node):
            if isinstance(node.value, str):
                value = node.value.replace('firmware/package_v37_g135', 'firmware/package_v38_g138')
                value = value.replace('57743bc105bc3d51b7fa65b44efd90afb022b2356d4e7846d470cc0c641c438a', digest)
                return ast.copy_location(ast.Constant(value), node)
            if type(node.value) is int and node.value == 135:
                return ast.copy_location(ast.Constant(138), node)
            return node

    def compiled(source, filename, mode, flags=0, dont_inherit=False, optimize=-1, **kwargs):
        if str(filename) == str(TARGET):
            tree = source if isinstance(source, ast.AST) else original(source, filename, mode, ast.PyCF_ONLY_AST)
            tree = ast.fix_missing_locations(Current().visit(tree))
            if flags & ast.PyCF_ONLY_AST:
                return tree
            return original(tree, filename, mode, flags, dont_inherit, optimize, **kwargs)
        return original(source, filename, mode, flags, dont_inherit, optimize, **kwargs)
    builtins.compile = compiled


def main():
    sys.dont_write_bytecode = True
    raw = DAT.read_bytes()
    bind(raw)
    api = runpy.run_path(str(TARGET), run_name='users_g138')
    users = [dict(base=i, levels=[0] * 11) for i in range(1, 9) if i != 5]
    users += [dict(base=5, levels=[0 if i == 0 else 1] + [0] * 10) for i in range(25)]
    fixture = api['replace_users'](raw, users)
    assert len(fixture) == len(raw) and api['replace_users'](fixture, []) == api['replace_users'](raw, [])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_bytes(fixture)
    print(json.dumps({'fixture': str(OUT.relative_to(ROOT)), 'sha256': hashlib.sha256(fixture).hexdigest(),
                      'base_sha256': hashlib.sha256(raw).hexdigest(), 'entries': len(users)}))


if __name__ == '__main__':
    main()
