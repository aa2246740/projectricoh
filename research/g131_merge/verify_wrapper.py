#!/usr/bin/python3
"""Check generation binding without changing the text range."""
from pathlib import Path
import ast
import dis
import hashlib
import json
import types

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / 'research/g131_merge'

def main():
    source = (WORK / 'run_existing.py').read_text()
    tree = ast.parse(source)
    function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'path_constants')
    namespace = dict(Path=Path, dis=dis, types=types, SOURCE_GENERATION=126, bindings=[], old_engines=(), old_packages=(), ENGINE=ROOT / 'firmware/engine_v51_g131', PACKAGE=ROOT / 'firmware/package_v36_g131', generation_parameters={'generation', 'gen', 'target_generation'}, generation_names={'GEN', 'GENERATION', 'TARGET_GENERATION', 'CURRENT_GENERATION'})
    exec(compile(ast.Module(body=[function], type_ignores=[]), str(WORK / 'run_existing.py'), 'exec'), namespace)
    original = compile('def check(generation, char):\n return generation == 126, 32 <= char <= 126\ndef header(data, char):\n return int.from_bytes(data[28:32], "big") == 127, char <= 126\n', '<generation-fields>', 'exec')
    current = {}
    exec(namespace['path_constants'](original), current)
    assert current['check'](131, 126) == (True, True)
    assert current['check'](131, 127) == (True, False)
    assert current['check'](131, 131) == (True, False)
    namespace['SOURCE_GENERATION'] = 127
    current = {}
    exec(namespace['path_constants'](original), current)
    raw = bytes(28) + (131).to_bytes(4, 'big')
    assert current['header'](raw, 126) == (True, True)
    assert current['header'](raw, 127) == (True, False)
    layout = json.loads((WORK / 'layout-bindings.json').read_text())
    fields = {item['field']: item for item in layout['bindings']}
    namespace['layout_fields'] = {item['before']: item for item in layout['bindings']}
    sample = compile('def snap(g, char):\n return g + ' + str(fields['busy']['before']) + ', g + ' +
        str(fields['settings_pending']['before']) + ', 32 <= char <= 126\n', '<named-layout>', 'exec')
    current = {}
    exec(namespace['path_constants'](sample), current)
    assert current['snap'](0, 126) == (fields['busy']['after'], fields['settings_pending']['after'], True)
    assert current['snap'](0, 127) == (fields['busy']['after'], fields['settings_pending']['after'], False)
    result = dict(status='PASS', wrapper_sha256=hashlib.sha256(source.encode()).hexdigest(), checks=7, ascii_max=126, generation=131, unscoped_integer_constants_replaced=0)
    (WORK / 'evidence/wrapper-check.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(dict(name='wrapper-check', returncode=0, counts=dict(checks=7))))

if __name__ == '__main__':
    main()
