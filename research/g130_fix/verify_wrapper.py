#!/usr/bin/python3
"""Check generation binding without changing the text range."""
from pathlib import Path
import ast
import dis
import hashlib
import json
import types

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / 'research/g130_fix'

def main():
    source = (WORK / 'run_existing.py').read_text()
    tree = ast.parse(source)
    function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'path_constants')
    namespace = dict(dis=dis, types=types, SOURCE_GENERATION=126, bindings=[], old_engines=(), old_packages=(), ENGINE=ROOT / 'firmware/engine_v50_h07', PACKAGE=ROOT / 'firmware/package_v36_g130', generation_parameters={'generation', 'gen', 'target_generation'}, generation_names={'GEN', 'GENERATION', 'TARGET_GENERATION', 'CURRENT_GENERATION'})
    exec(compile(ast.Module(body=[function], type_ignores=[]), str(WORK / 'run_existing.py'), 'exec'), namespace)
    original = compile('def check(generation, char):\n return generation == 126, 32 <= char <= 126\ndef header(data, char):\n return int.from_bytes(data[28:32], "big") == 127, char <= 126\n', '<generation-fields>', 'exec')
    current = {}
    exec(namespace['path_constants'](original), current)
    assert current['check'](130, 126) == (True, True)
    assert current['check'](130, 127) == (True, False)
    assert current['check'](130, 130) == (True, False)
    namespace['SOURCE_GENERATION'] = 127
    current = {}
    exec(namespace['path_constants'](original), current)
    raw = bytes(28) + (130).to_bytes(4, 'big')
    assert current['header'](raw, 126) == (True, True)
    assert current['header'](raw, 127) == (True, False)
    result = dict(status='PASS', wrapper_sha256=hashlib.sha256(source.encode()).hexdigest(), checks=5, ascii_max=126, generation=130, unscoped_integer_constants_replaced=0)
    (WORK / 'evidence/wrapper-check.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(dict(name='wrapper-check', returncode=0, counts=dict(checks=5))))

if __name__ == '__main__':
    main()
