"""Produce old and current target layouts for named observations."""
from pathlib import Path
import json
import runpy
import struct
import subprocess

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / 'research/g135_v37'

def main():
    folder = WORK / 'local/layout-bindings'
    folder.mkdir(parents=True, exist_ok=True)
    elf_type = runpy.run_path(str(ROOT / 'firmware/stage2l_switch/tools/build.py'))['Elf']
    names = ['bytes', 'epoch', 'current', 'confirmed', 'tweak', 'confirmed_tweak', 'list',
             'stock', 'live', 'staging', 'ready', 'bound', 'busy', 'committed', 'uncertain',
             't_checked', 't_warn', 't_pending', 'neighbor', 'neighbor_valid', 'stage',
             'remember_checked', 'confirmed_valid', 'previewing', 'view_lost',
             'write_started', 'recheck', 'settings_pending']
    layouts = {}
    for label, tree in [('previous', 'engine_v48_own'), ('current', 'engine_v53_g135')]:
        product = ROOT / 'firmware' / tree / 'candidate/containers/product'
        out = folder / (label + '.o')
        command = [str(ROOT / 'research/tooling_m32r_c/prefix/gcc/bin/m32r-elf-gcc'),
            '-std=c11', '-Os', '-ffreestanding', '-fno-builtin', '-fpic', '-m32r',
            '-mmodel=medium', '-msdata=none', '-G0', '-I',
            str(product / 'src/firmware/engine/core'), '-c', str(WORK / 'core_layout.c'), '-o', str(out)]
        result = subprocess.run(command, capture_output=True, text=True, timeout=3600)
        (folder / (label + '.log')).write_text(result.stdout + result.stderr)
        assert result.returncode == 0, 'target layout compilation'
        elf = elf_type(out)
        section = next(s for s in elf.sections if s['name'] == '.layout')
        values = struct.unpack('>' + str(len(names)) + 'I', elf.content(section))
        layouts[label] = dict(zip(names, values))
    bindings = [dict(field=name, before=layouts['previous'][name], after=layouts['current'][name])
                for name in names if layouts['previous'][name] != layouts['current'][name]]
    (WORK / 'layout-bindings.json').write_text(json.dumps(dict(layouts=layouts, bindings=bindings), indent=2) + '\n')
    print(json.dumps(dict(name='layout-bindings', returncode=0, counts=dict(fields=len(bindings)))))

if __name__ == '__main__':
    main()
