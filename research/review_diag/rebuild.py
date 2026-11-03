"""Rebuild original sources with all outputs confined to this review's local/."""
from pathlib import Path
import copy
import importlib.util
import json
import os
import plistlib
import shutil
import struct
import subprocess
import sys

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
ENGINE = ROOT / 'firmware/engine_diag_v1'
sys.path.insert(0, str(ROOT / 'research/diag_dat_v1'))
import scope
scope.ALLOWED = (OUT,)


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def main():
    upstream = load(ENGINE / 'build_diag.py', 'review_original_build')
    c, services = upstream.c, upstream.service_build
    original_product = c.PRODUCT
    work = OUT / 'local/rebuild/candidate'
    c.HERE, c.LOCAL = work, work / 'local'
    c.save = scope.save

    def guard():
        info = plistlib.loads(subprocess.check_output(['/usr/sbin/diskutil', 'info', '-plist', '/Volumes/Workspace']))
        assert info['FilesystemType'] == 'apfs'
        assert info['VolumeUUID'] == '14BE04EB-AF49-497E-B36A-B078B2F7C5E8'
        assert info['WritableVolume'] and info['WritableMedia']
        (c.LOCAL / 'tmp').mkdir(parents=True, exist_ok=True)

    c.guard = guard
    guard()
    (work / 'engine_services').mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ENGINE / 'candidate/engine_services/library.ld', work / 'engine_services/library.ld')
    services.LOCAL = c.LOCAL / 'resident'
    services.main()
    pack = load(original_product / 'pack.py', 'review_pack')
    model = upstream.model(pack)
    inert, _, _ = pack.pack_model(copy.deepcopy(model), upstream.GENERATION)
    build = load(original_product / 'build.py', 'review_link')
    build.HERE = work / 'containers/product'
    build.HERE.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(original_product / 'engine.ld', build.HERE / 'engine.ld')
    build.LOCAL = c.LOCAL / 'product-r13'
    build.LOCAL.mkdir(exist_ok=True)
    build.guard, build.run = guard, c.run
    build.sources = lambda: [(original_product / 'diag.c', False),
                            (original_product / 'src/firmware/engine/core/eng_mem.c', False)]
    layout = build.build(len(inert)-256-len(pack.STUB), lto=True)
    built = build.LOCAL / 'm32r-lto'
    reloc = (built / 'reloc.bin').read_bytes()
    identity = json.loads((ROOT / 'firmware/resident_v36/local/resident/trust.json').read_text())
    blob, trust, stats = pack.pack_model(model, upstream.GENERATION,
        engine=(built / 'engine.bin').read_bytes(),
        relocations=[struct.unpack_from('>II', reloc, i) for i in range(0, len(reloc), 8)],
        bss=layout['bss_bytes'], entry=layout['entries']['ig_bootstrap'],
        resident_id=bytes.fromhex(identity['resident_build_id']),
        abi_id=bytes.fromhex(identity['resident_abi_id']))
    target = OUT / 'local/rebuild/GXRCE.DAT'
    target.write_bytes(blob)
    comparisons = {}
    originals = ENGINE / 'candidate/local/full-r13'
    for name in ('engine.bin', 'engine.elf', 'reloc.bin'):
        comparisons[name] = dict(equal=(built / name).read_bytes() == (originals / name).read_bytes(),
            rebuilt_sha256=scope.sha(built / name), original_sha256=scope.sha(originals / name))
    comparisons['GXRCE.DAT'] = dict(equal=blob == scope.PACKAGE.joinpath('local/SD_ROOT/GXRCE.DAT').read_bytes(),
        rebuilt_sha256=scope.sha(target), original_sha256=scope.sha(scope.PACKAGE / 'local/SD_ROOT/GXRCE.DAT'))
    original_archive = ENGINE / 'candidate/local/resident/engine-services/libgxr_services.a'
    rebuilt_archive = services.LOCAL / 'engine-services/libgxr_services.a'
    comparisons['service_archive'] = dict(equal=original_archive.read_bytes() == rebuilt_archive.read_bytes(),
        rebuilt_sha256=scope.sha(rebuilt_archive), original_sha256=scope.sha(original_archive))
    record=dict(comparisons=comparisons, output_root=str(OUT / 'local/rebuild'),
        source_root=str(ENGINE), status='PASS' if all(x['equal'] for x in comparisons.values()) else 'MISMATCH')
    scope.save(OUT / 'evidence/rebuild.json', record)
    print(json.dumps(record, indent=2), flush=True)
    assert record['status'] == 'PASS'


if __name__ == '__main__':
    main()
