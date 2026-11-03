#!/usr/bin/python3
"""Repeat a sealed function check with a new output and private temporary path."""
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import plistlib
import re
import shutil
import subprocess
import sys
import types

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
TEMP = Path('/Volumes/Workspace/Scratch/tmp/projectricoh/review-v310-body-r1')
SCRIPTS = dict(mode='mode_contract.py', menu='menu_verify.py', native='native_checks.py',
               checksum='checksum_check.py', key='key_checks.py')


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--kind', choices=tuple(SCRIPTS), required=True)
    p.add_argument('--backend', choices=('c', 'python'), required=True)
    p.add_argument('--label', required=True)
    a = p.parse_args()
    assert os.getpriority(os.PRIO_PROCESS, 0) >= 10
    assert re.fullmatch(r'[A-Za-z0-9-]{1,64}', a.label)
    disk = plistlib.loads(subprocess.check_output(['diskutil', 'info', '-plist', '/Volumes/Workspace']))
    assert disk['VolumeUUID'] == '14BE04EB-AF49-497E-B36A-B078B2F7C5E8'
    assert disk.get('FilesystemType', '').lower() == 'apfs'
    assert disk.get('MountPoint') == '/Volumes/Workspace' and not disk.get('ReadOnlyVolume', False)
    output = HERE / 'local/reruns' / a.label / (a.kind + '-' + a.backend + '.json')
    private = TEMP / ('rerun-' + a.label + '-' + a.kind + '-' + a.backend)
    assert not output.exists() and not private.exists()
    output.parent.mkdir(parents=True, exist_ok=True)
    private.mkdir(parents=True)
    script = HERE / SCRIPTS[a.kind]
    tree = ast.parse(script.read_text(), filename=str(script))
    count = 0
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        names = [v.id for v in node.targets if isinstance(v, ast.Name)]
        if 'target' in names:
            node.value = ast.Name(id='_RERUN_TARGET', ctx=ast.Load())
            count += 1
        if 'TEMP' in names:
            node.value = ast.Name(id='_RERUN_TEMP', ctx=ast.Load())
    assert count == (2 if a.kind == 'key' else 1)
    ast.fix_missing_locations(tree)
    module = types.ModuleType('review_function_rerun')
    module.__file__ = str(script)
    module._RERUN_TARGET = output
    module._RERUN_TEMP = private
    sys.modules[module.__name__] = module
    sys.argv = [str(script), '--backend', a.backend]
    try:
        exec(compile(tree, str(script), 'exec'), module.__dict__)
        if a.kind == 'key':
            module.verify(a.backend)
        else:
            module.main()
        result = json.loads(output.read_text())
        result['rerun'] = dict(driver_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            original_source_sha256=hashlib.sha256(script.read_bytes()).hexdigest(),
            AST_changes='Only output target and temporary path; original input, CPU, assertions and case bytes unchanged',
            private_tmp_removed=True)
        output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
        print(json.dumps(dict(output=str(output.relative_to(ROOT)), status=result['status'])))
    finally:
        if private.exists():
            assert private.parent.resolve() == TEMP and not private.is_symlink()
            shutil.rmtree(private)
        if TEMP.is_dir() and not any(TEMP.iterdir()):
            TEMP.rmdir()


if __name__ == '__main__':
    main()
