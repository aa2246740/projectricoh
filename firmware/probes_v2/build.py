#!/usr/bin/env python3
"""Build three uncontained, offline-only engines; never emits a card package."""
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import struct
import sys

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def main():
    s = module(HERE / 'support.py', 'pv_support')
    volume = s.preflight()
    resident = module(ROOT / 'firmware/resident_v2/build.py', 'pv_readonly_resident_build')
    out = s.LOCAL / 'build'
    out.mkdir(exist_ok=True)
    flags = [*resident.FLAGS, '-mmodel=medium', '-fno-jump-tables', '-fno-tree-switch-conversion']
    tools = [resident.GCC, resident.LD, resident.OBJDUMP]
    results = {}
    commands = []

    def run(argv, log):
        p = s.run(argv, out / (log+'.log'))
        commands.append(dict(argv=[str(x) for x in argv], returncode=p.returncode, log=log+'.log'))
        (out / 'commands.json').write_text(json.dumps(commands, indent=2)+'\n')
        return p

    layout_source = out/'layout.c'
    layout_source.write_text('#include "probes.h"\nconst unsigned pv_layout[] = {'
                             'sizeof(PvState),sizeof(PvInvocation),sizeof(RvApi),'
                             'offsetof(PvState,rows),offsetof(PvState,glyphs),'
                             'offsetof(PvState,table)};\n')
    run([resident.GCC, *flags, '-I', HERE, '-c', layout_source, '-o', out/'layout.o'], 'target-layout')
    layout_elf = s.Elf(out/'layout.o')
    symbol = layout_elf.symbols['pv_layout']
    raw_layout = layout_elf.content(layout_elf.sections[symbol['section']])
    values = struct.unpack_from('>6I', raw_layout, symbol['value'])
    layout = dict(zip(('context_bytes', 'invocation_bytes', 'api_bytes', 'rows_offset', 'glyphs_offset', 'table_offset'), values))
    (out/'target-layout.json').write_text(json.dumps(layout, indent=2)+'\n')
    for number, name in enumerate(('life', 'notice', 'view'), 1):
        dest = out / name
        dest.mkdir(exist_ok=True)
        objects = []
        relocation_count = 0
        for source in ('entry.S', 'engine.c', 'runtime.c'):
            obj = dest / (Path(source).stem+'.o')
            objects.append(obj)
            run([resident.GCC, *flags, f'-DPV_ENGINE={number}', '-c', HERE/source, '-o', obj], name+'-compile-'+source)
            rel = run([resident.OBJDUMP, '-r', obj], name+'-relocations-'+source).stdout
            for kind in re.findall(r'\bR_M32R_\w+', rel):
                if not re.fullmatch(r'R_M32R_(10|18|26)_PCREL(?:_RELA)?', kind):
                    raise RuntimeError(f'{name}: forbidden link relocation {kind}')
                relocation_count += 1
        elf_path = dest / 'engine.elf'
        run([resident.LD, '--no-undefined', '--orphan-handling=error', '-T', HERE/'engine.ld',
             '-Map='+str(dest/'engine.map'), '-o', elf_path, *objects], name+'-link')
        elf = s.Elf(elf_path)
        code = elf.content(elf.section('.engine'))
        if elf.entry != 0 or elf.section('.engine')['va'] != 0:
            raise RuntimeError('engine did not link at zero')
        if any(v['section'] == 0 for v in elf.symbols.values()):
            raise RuntimeError('undefined symbol')
        if any(sec['size'] for sec in elf.sections if sec['type'] in (4, 9)):
            raise RuntimeError('unresolved runtime relocations')
        entry_names = ('pv_entry', 'pv_entry_init', 'pv_entry_menu', 'pv_entry_event',
                       'pv_entry_panel_open', 'pv_entry_panel_event', 'pv_entry_panel_abort',
                       'pv_entry_apply', 'pv_entry_shutdown', 'pv_entry_abort')
        for i, symbol in enumerate(entry_names):
            if elf.symbols[symbol]['value'] != i*16:
                raise RuntimeError(f'bad entry thunk {symbol}')
        run([resident.OBJDUMP, '-d', elf_path], name+'-disassembly')
        # Extraction uses the measured ELF section, not an alternate linker.
        (dest / 'engine.bin').write_bytes(code)
        (dest / 'relocations.bin').write_bytes(b'')
        stack = []
        for path in sorted(dest.glob('*.su')):
            for line in path.read_text().splitlines():
                location, size, allocation = line.rsplit('\t', 2)
                stack.append(dict(function=location.rsplit(':', 1)[-1], bytes=int(size), allocation=allocation))
        metadata = dict(engine=name, engine_kind=number, engine_abi_version=1, linked_base=0,
                        engine_bytes=len(code), engine_sha256=hashlib.sha256(code).hexdigest(),
                        bootstrap_engine_offset=0, entry_engine_offsets={n: i*16 for i, n in enumerate(entry_names)},
                        runtime_relocations=[], link_pcrel_relocations=relocation_count,
                        bss_bytes=0, context_layout='PvState in probes.h',
                        context_bytes=layout['context_bytes'], invocation_bytes=layout['invocation_bytes'],
                        native_ui_state_bytes=None, ready_ui_capability=1<<17,
                        defaults=dict(witness_bytes=256, witness_usage=2, reference_valid=False,
                                      reference_replica=0,
                                      writes_enabled=False, active_rpc=False, active_preview=False),
                        capacity_probe=dict(order_kib=[64,48,40,32,16], free_immediately=True,
                                            timings=['first_menu','after_playback','after_sleep'], touches_blocks=False),
                        stack_frames=stack, max_static_frame=max((r['bytes'] for r in stack), default=0),
                        final_container=False, resident_bound=False, camera_executed=False)
        (dest / 'metadata.json').write_text(json.dumps(metadata, ensure_ascii=False, indent=2)+'\n')
        results[name] = dict(bytes=len(code), sha256=metadata['engine_sha256'],
                             runtime_relocations=0, link_pcrel_relocations=relocation_count,
                             max_static_frame=metadata['max_static_frame'])
        print(f'{name}: code={len(code)} B, runtime relocations=0, max frame={metadata["max_static_frame"]} B')
    # Relocation invariance is also checked at a second link base using the
    # same objects; the build fails if any address-dependent byte appears.
    script = (HERE / 'engine.ld').read_text().replace('. = 0;', '. = 0x21000000;')
    script = script.replace('pv_entry == 0', 'pv_entry == 0x21000000')
    script = script.replace('pv_entry_init == 16 && pv_entry_abort == 144',
                            'pv_entry_init == 0x21000010 && pv_entry_abort == 0x21000090')
    (out/'invariance.ld').write_text(script)
    for name in results:
        dest = out/name
        run([resident.LD, '--no-undefined', '--orphan-handling=error', '-T', out/'invariance.ld',
             '-o', dest/'invariance.elf', dest/'entry.o', dest/'engine.o', dest/'runtime.o'], name+'-invariance-link')
        relinked = s.Elf(dest/'invariance.elf')
        if relinked.content(relinked.section('.engine')) != (dest/'engine.bin').read_bytes():
            raise RuntimeError(f'{name}: position-dependent code bytes')
        results[name]['second_base_byte_identical'] = True
    summary = dict(volume=volume, flags=flags, flags_source='firmware/resident_v2/build.py',
                   c_model_override='medium, same as resident_v2/build.py',
                   extra_flags=['-fno-jump-tables','-fno-tree-switch-conversion'],
                   extra_flags_reason='prevent implicit jump and integer lookup tables with absolute addresses',
                   tools={str(p.relative_to(ROOT)): s.sha(p) for p in tools},
                   source_hashes={p.name:s.sha(p) for p in (HERE/'engine.c', HERE/'probes.h', HERE/'entry.S', HERE/'runtime.c', HERE/'engine.ld')},
                   abi_sha256=s.sha(ROOT/'firmware/resident_v2/abi.h'), target_layout=layout, results=results,
                   container_packaged=False, camera_executed=False)
    (out/'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2)+'\n')


if __name__ == '__main__':
    main()
