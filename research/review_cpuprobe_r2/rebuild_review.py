"""Rebuild the service archive and DAT without writing to the source tree."""
from pathlib import Path
import copy
import importlib.util
import json
import os
import struct
import subprocess
import sys
import time
import types

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import review_scope as rs
rs.enable()
ROOT = rs.ROOT
TREE = ROOT / 'firmware/engine_cpuprobe_v38'
CANDIDATE = TREE / 'candidate'
PRODUCT = CANDIDATE / 'containers/product'
WORK = rs.TEMP / 'rebuild'
COMMANDS = []


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def run(args, label, **options):
    arguments = [str(a) for a in args]
    started = time.monotonic()
    environment = dict(os.environ, TMPDIR=str(rs.TEMP), LC_ALL='C', PYTHONDONTWRITEBYTECODE='1')
    result = subprocess.run(arguments, cwd=ROOT, env=environment, capture_output=True,
                            text=True, timeout=1800)
    log = HERE / 'rebuild-logs' / (label + '.log')
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text(result.stdout + result.stderr)
    COMMANDS.append(dict(argv=arguments, label=label, returncode=result.returncode,
                         seconds=round(time.monotonic() - started, 3)))
    assert result.returncode == 0, (label, result.stderr[-1500:])
    return result


def main():
    started = time.monotonic()
    WORK.mkdir(parents=True, exist_ok=True)
    image_reader = load('review_image_reader', ROOT / 'tools/native_harness/image_loader.py')
    body_path = ROOT / 'firmware/package_v38_g137/local/SD_ROOT/ilaunch3'
    image = image_reader.Image(body_path)
    resident_path = ROOT / 'firmware/resident_v38/local/resident/build/resident.elf'
    resident = image_reader.Elf(resident_path)
    resident_sections = []
    for section in resident.sections:
        if section['name'] in ('.resident', '.root_pins'):
            assert image.bytes_at(section['base'], section['size']) == section['data']
            resident_sections.append(dict(name=section['name'], address=hex(section['base']), bytes=section['size']))
    assert image.bytes_at(0x20054700, 244) == bytes([255]) * 244
    assert any(s.bss <= 0x205a2944 < s.bss + s.bss_size for s in image.sections)
    sys.path.insert(0, str(ROOT / 'research/cpu_speed_probe'))
    import scope
    scope.OUTPUTS = rs.ALLOWED
    scope.freeze_check = rs.verify
    sys.path.insert(0, str(CANDIDATE))
    import common as c
    c.LOCAL = WORK / 'candidate'
    c.LOCAL.mkdir(parents=True, exist_ok=True)
    c.SCRATCH = rs.TEMP
    c.guard = lambda: None
    c.run = run
    c.save = rs.save
    c.write = lambda path, value: (Path(path).parent.mkdir(parents=True, exist_ok=True), Path(path).write_bytes(value))[-1]
    source = (CANDIDATE / 'service_build.py').read_text()
    for value in ('archive', 'elf'):
        old = value + '.relative_to(c.HERE)'
        assert source.count(old) == 1
        source = source.replace(old, value + '.relative_to(c.LOCAL)')
    service = types.ModuleType('service_build')
    service.__file__ = str(CANDIDATE / 'service_build.py')
    sys.modules['service_build'] = service
    exec(compile(source, service.__file__, 'exec'), service.__dict__)
    service.main()
    archive = c.LOCAL / 'resident/engine-services/libgxr_services.a'
    original_archive = CANDIDATE / 'local/resident/engine-services/libgxr_services.a'
    assert archive.read_bytes() == original_archive.read_bytes()

    sys.path.insert(0, str(TREE))
    import cp_model
    data = CANDIDATE / 'local/gen/cp_data.c'
    assert cp_model.c_source().encode() == data.read_bytes()
    build = load('review_link', PRODUCT / 'build.py')
    build.run = run
    build.guard = lambda: None
    build.LOCAL = WORK / 'product'
    build.LOCAL.mkdir(parents=True, exist_ok=True)
    build.sources = lambda: [(PRODUCT / 'probe.c', False), (PRODUCT / 'kernel.c', False),
        (PRODUCT / 'cpkern.S', False), (data, False),
        (PRODUCT / 'src/firmware/engine/core/eng_mem.c', False)]
    expected = json.loads((CANDIDATE / 'local/full-r1/layout.json').read_text())
    layout = build.build(expected['data_bytes'], lto=True)
    built = build.LOCAL / 'm32r-lto'
    for name in ('engine.bin', 'reloc.bin'):
        assert (built / name).read_bytes() == (CANDIDATE / 'local/full-r1' / name).read_bytes(), name
    bp = load('review_build_probe', TREE / 'build_probe.py')
    pack = c.load(PRODUCT / 'pack.py', 'review_pack')
    modules = bp.model(pack)
    trust = json.loads((ROOT / 'firmware/resident_v38/local/resident/trust.json').read_text())
    relocation = (built / 'reloc.bin').read_bytes()
    blob, _, stats = pack.pack_model(modules, bp.GENERATION,
        engine=(built / 'engine.bin').read_bytes(),
        relocations=[struct.unpack_from('>II', relocation, i) for i in range(0, len(relocation), 8)],
        bss=layout['bss_bytes'], entry=layout['entries']['ig_bootstrap'],
        resident_id=bytes.fromhex(trust['resident_build_id']), abi_id=bytes.fromhex(trust['resident_abi_id']))
    dat = ROOT / 'firmware/package_v38_cpuprobe/SD_ROOT/GXRCE.DAT'
    assert blob == dat.read_bytes()
    target = WORK / 'GXRCE.DAT'
    target.write_bytes(blob)
    rs.save(HERE / 'rebuild-result.json', dict(status='PASS', dat_sha256=rs.digest(target),
        dat_bytes=len(blob), service_archive_sha256=rs.digest(archive),
        engine_sha256=rs.digest(built / 'engine.bin'), layout=layout, stats=stats,
        commands=COMMANDS, seconds=round(time.monotonic() - started, 3),
        body_sha256=rs.digest(body_path), resident_elf_sha256=rs.digest(resident_path),
        resident_sections_matching_body=resident_sections, root_initial_ff_bytes=244, cursor_cache_in_bss=True,
        method='unchanged compiler and source; output paths and review guards redirected; archive bytes compared before link'))
    print('REBUILD_PASS', len(blob), rs.digest(target), flush=True)


if __name__ == '__main__':
    main()
