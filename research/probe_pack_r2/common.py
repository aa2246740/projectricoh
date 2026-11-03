"""Paths, input identity, and receipts for the local colour probe package."""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import plistlib
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
TMP = Path('/Volumes/Workspace/Scratch/tmp/projectricoh/probe-pack-r2')
PACKAGE = ROOT / 'firmware/package_v39_g154_probe2'
BASE = ROOT / 'firmware/package_v39_g154_looks18_test'
ENGINE = ROOT / 'firmware/engine_v65_g154_looks'
BASE_SHA = '5f6191c88e7691472541dce245df67679390aa850ffd110e8f8eb35f4b24c681'
BODY_SHA = '8233a1c464b29ba88cfdfce1d083b9bf652586edeb216cacf6f16cf36788b25d'
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT / 'research/v39_g153'))
from dat_format import (KINDS, LENGTHS, OFFSETS, CRC_FIELDS, align4, crc, u16, u32,
                        sections, seal, expand, expand_effect, refresh_entry, strict_effects)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def guard(create_tmp=True):
    info = plistlib.loads(subprocess.check_output(
        ['/usr/sbin/diskutil', 'info', '-plist', '/Volumes/Workspace']))
    assert info['VolumeUUID'] == '14BE04EB-AF49-497E-B36A-B078B2F7C5E8'
    assert info['FilesystemType'] == 'apfs' and info['WritableVolume'] and info['WritableMedia']
    assert os.path.ismount('/Volumes/Workspace')
    assert sha((BASE / 'local/SD_ROOT/GXRCE.DAT').read_bytes()) == BASE_SHA
    assert sha((BASE / 'local/SD_ROOT/ilaunch3').read_bytes()) == BODY_SHA
    if create_tmp:
        TMP.mkdir(parents=True, exist_ok=True)
    os.environ.update(TMPDIR=str(TMP), PYTHONDONTWRITEBYTECODE='1', GIT_OPTIONAL_LOCKS='0')


def freeze():
    paths = set()
    for folder in (ENGINE, ROOT / 'tools/gxr_emulator_batch', ROOT / 'tools/gxr_emulator_standby',
                   ROOT / 'tools/native_harness_c'):
        paths.update(p for p in folder.rglob('*') if p.is_file() and 'local' not in p.relative_to(folder).parts
                     and p.suffix in ('.py', '.c', '.h', '.S', '.ld'))
    paths.update(p for p in (BASE / 'local/SD_ROOT').iterdir() if p.is_file())
    paths.update(p for p in (BASE / 'local/build').iterdir() if p.is_file())
    return {str(p.relative_to(ROOT)): sha(p.read_bytes()) for p in sorted(paths)}
