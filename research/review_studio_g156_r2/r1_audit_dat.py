"""Read frozen inputs; write evidence only beside this file. Run with python -I -B."""
from pathlib import Path
import ctypes as CT
from dataclasses import replace
import hashlib
import importlib.util
import json
import os
import struct
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
STUDIO = Path('/Volumes/Workspace/Scratch/worktrees/gxr-studio/g156-codec')
sys.dont_write_bytecode = True


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def save(name, data):
    (HERE/'evidence'/name).write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n')


def main():
    sys.path.insert(0, str(ROOT/'research/g156'))
    import common as C
    original_local = C.LOCAL
    C.HERE = HERE/'parent-static'
    C.TMP = C.HERE/'tmp'
    C.ALLOWED = (HERE,)
    (C.HERE/'evidence').mkdir(parents=True, exist_ok=True)
    C.setup()
    # Execute the parent's actual static gate entry point with only output paths changed.
    parent_static = load('review_parent_r2_static', ROOT/'research/g156/r2_static.py')
    parent_static.main()
    dc = load('review_studio_datcodec', STUDIO/'src/gxr_studio/camdata/datcodec.py')
    D = C.DF
    formatter = sys.modules['g156_r2_format']
    gate156 = CT.CDLL(str(formatter.TMP/'parsers.dylib'))
    gate156.check_dat.argtypes = [CT.c_void_p, CT.c_size_t, CT.c_void_p, CT.c_uint]
    # Compile the unmodified previous-generation C gate as the control as well.
    old_format = load('review_old_format', ROOT/'research/v39_g153/format_checks.py')
    old_format.PRODUCT = C.BASE/'candidate/containers/product'
    old_format.HERE = HERE/'tmp/gate155'
    old_format.TMP = old_format.HERE/'format'
    (old_format.HERE/'evidence').mkdir(parents=True, exist_ok=True)
    gate155 = old_format.library()

    def check(raw, generation):
        lib = gate156 if generation == 156 else gate155
        return [lib.check_dat(CT.create_string_buffer(raw), len(raw),
                             CT.create_string_buffer(formatter.trust(raw)), unit)
                for unit in range(3)]

    packages = {}
    results = []
    users_cases = [[], [{'base': 5, 'levels': [1]+[0]*10}],
                   [{'base': 2, 'levels': [0]*11} for _ in range(30)]]
    for name in ('g156', 'g156_test', 'g155c', 'g155c_test'):
        raw = (ROOT/f'firmware/package_v310_{name}/GXRCE.DAT').read_bytes()
        dat = dc.parse(raw)
        packages[name] = raw, dat
        packed = dc.pack(dat)
        assert packed == raw
        assert check(raw, dat.generation) == [0, 0, 0]
        directory = D.sections(raw)[2][0]
        banks = [D.u32(raw, directory+64*unit+16) for unit in range(3)]
        assert [D.u32(raw, at+16) for at in banks] == [155]*3
        for unit in range(3):
            assert dc.crc(dat.entry_of(unit, 4)[:448]) == dc.STOCK_ENTRY_CRC[unit]
            assert dat.modules[unit].crc_pin == dc.PIN_CRC32[unit]
            for slot in dat.modules[unit].entries:
                assert dat.entry_of(unit, slot) == D.expand(raw, unit, slot)
        assert all(look.entry == D.expand_effect(raw, index)
                   for index, look in enumerate(dat.looks))
        edits = []
        for users in users_cases:
            output = dc.pack(dc.replace_users(dat, users))
            again = dc.parse(output)
            assert again.users == users
            assert check(output, dat.generation) == [0, 0, 0]
            ext = D.sections(raw)[6][0]+dc.LEGACY_BYTES
            assert output[:20] == raw[:20] and output[28:ext] == raw[28:ext]
            assert output[ext+dc.EXT_BYTES:] == raw[ext+dc.EXT_BYTES:]
            assert output[20:28] != raw[20:28] or users == dat.users
            for at in banks:
                assert output[at:at+1056] == raw[at:at+1056]
            for unit in range(3):
                assert again.modules[unit].pin == dat.modules[unit].pin
                assert all(again.entry_of(unit, slot) == dat.entry_of(unit, slot)
                           for slot in dat.modules[unit].entries)
            edits.append(dict(user_count=len(users), sha256=digest(output),
                              c_gate=check(output, dat.generation),
                              changed_offsets=[i for i, pair in enumerate(zip(raw, output)) if pair[0] != pair[1]]))
        invalid_banks = []
        for unit in range(3):
            for generation in (0, 127, 154, 156, 157):
                output = bytearray(raw)
                at = banks[unit]
                struct.pack_into('>I', output, at+16, generation)
                struct.pack_into('>I', output, at+28, dc.crc(output[at:at+28]))
                output = D.seal(output)
                try:
                    dc.parse(output)
                except dc.DatError as error:
                    assert str(error) == '配方库头、CRC 或代数不合格'
                    invalid_banks.append(dict(unit=unit, bank_generation=generation, rejected=str(error)))
                else:
                    raise AssertionError(('wrong bank accepted', name, unit, generation))
        results.append(dict(package=name, generation=dat.generation, bytes=len(raw),
                            sha256=digest(raw), round_trip_sha256=digest(packed),
                            bank_generations=[155]*3, c_gate=check(raw, dat.generation),
                            original_records_pins_and_looks_equal=True, edits=edits,
                            invalid_banks=invalid_banks))
    # Check every other registered generation, not only the four in the PR's new test.
    fixture_names = {
        127:'package_v36_g127/local/SD_ROOT',129:'package_v36_g129/local/SD_ROOT',
        131:'package_v36_g131/local/SD_ROOT',135:'package_v37_g135/local/SD_ROOT',
        137:'package_v38_g137/local/SD_ROOT',138:'package_v38_g138/SD_ROOT',
        150:'package_v38_g150',152:'package_v38_g152',153:'package_v39_g153',
        154:'package_v39_g154',155:'package_v310_g155c'}
    older = []
    for generation, folder in fixture_names.items():
        path = ROOT/'firmware'/folder/'GXRCE.DAT'
        if generation in (150, 152, 153, 154):
            package = ROOT/'firmware'/folder
            path = package/'SD_ROOT/GXRCE.DAT'
            if not path.is_file():
                path = package/'local/SD_ROOT/GXRCE.DAT'
        if not path.is_file():
            older.append(dict(generation=generation, absent=str(path)))
            continue
        raw = path.read_bytes()
        assert dc.parse(raw).generation == generation
        assert dc.PROFILES[generation].bank_generation == generation
        for unit in range(3):
            at = D.u32(raw, D.sections(raw)[2][0]+64*unit+16)
            output = bytearray(raw)
            wrong = 156 if generation == 155 else 155
            struct.pack_into('>I', output, at+16, wrong)
            struct.pack_into('>I', output, at+28, dc.crc(output[at:at+28]))
            try:
                dc.parse(D.seal(output))
            except dc.DatError as error:
                assert str(error) == '配方库头、CRC 或代数不合格'
            else:
                raise AssertionError(('older generation relaxed', generation, unit))
        older.append(dict(generation=generation, sha256=digest(raw), rejected_wrong_bank_all_three=True))

    # Execute the real embedded M32R eng_data_accept, using symbols from its matching ELF.
    sys.path.insert(0, str(ROOT/'tools/native_harness_c'))
    import python_backend as PB
    PB.CACHE = HERE/'tmp/m32r-decode'
    elf_reader = load('review_elf_reader', ROOT/'firmware/stage2l_switch/tools/build.py')

    def m32r(raw, engine_folder, build):
        elf_path = ROOT/'firmware'/engine_folder/'candidate/local'/build/'engine.elf'
        elf = elf_reader.Elf(elf_path)
        code = next(section for section in elf.sections if section['name'] == '.engine')
        assert elf.content(code) == raw[256:256+code['size']]
        rows = []
        for unit in range(3):
            base = 0x21004000
            image = bytearray(raw)+bytes(D.u32(raw,116))
            at, length = D.sections(raw)[1]
            for offset in range(at, at+length, 8):
                patch, target = struct.unpack_from('>II', raw, offset)
                struct.pack_into('>I', image, patch, base+target)
            view = struct.pack('>5I',base,len(raw),D.u32(raw,28),D.u32(raw,112),D.u32(raw,116))
            view += b''.join(struct.pack('>II', at, n) for at,n in D.sections(raw))
            view += struct.pack('>HH4B',8,28,unit,1,0,0)
            backend = PB.PythonBackend()
            backend.map(base,image,True)
            backend.map(0x22000000,bytes(0x20000),True)
            backend.write(0x22000100,view)
            backend.set_reg('r15',0x2201fff0)
            stop = backend.call(base+elf.symbols['eng_data_accept']['value'],[0x22000100],0x7ffffff0,20000)
            assert stop.reason == 'return', (stop.reason, stop.detail)
            rows.append(dict(unit=unit, result=backend.get_reg('r0'), instructions=stop.steps))
        return dict(elf_sha256=digest(elf_path.read_bytes()), rows=rows)

    mixed = []
    for name in ('g155c','g155c_test'):
        raw, dat = packages[name]
        changed = bytearray(raw)
        struct.pack_into('>I',changed,28,156)
        changed = D.seal(changed)
        accepted = dc.parse(changed)
        assert accepted.generation == 156 and accepted.engine == dat.engine
        assert dc.pack(accepted) == changed
        build = 'boot-on' if name.endswith('_test') else 'boot-off'
        control = m32r(raw,'engine_v67_g155c',build)
        rejection = m32r(changed,'engine_v67_g155c',build)
        assert [row['result'] for row in control['rows']] == [0,0,0]
        assert [row['result'] for row in rejection['rows']] == [1,1,1]
        mixed.append(dict(case=name+'-only-outer156', sha256=digest(changed),
                          studio_accepts=True, round_trip_identical=True,
                          c_gate156=check(changed,156), embedded_engine_control=control,
                          embedded_engine_rejects=rejection,
                          changed_offsets=[i for i,pair in enumerate(zip(raw,changed)) if pair[0]!=pair[1]]))
        target_name = 'g156_test' if name.endswith('_test') else 'g156'
        new_raw, new_dat = packages[target_name]
        hybrid = dc.pack(replace(dat,generation=156,engine=new_dat.engine,
                                relocations=new_dat.relocations,entry=new_dat.entry,bss=new_dat.bss))
        try:
            dc.parse(hybrid)
        except dc.DatError as error:
            mixed.append(dict(case=name+'-with-real-g156-engine',studio_accepts=False,reason=str(error)))
        else:
            mixed.append(dict(case=name+'-with-real-g156-engine',studio_accepts=True,
                              sha256=digest(hybrid),c_gate156=check(hybrid,156),
                              output_bss_start=len(hybrid),engine_linked_bss_start=len(new_raw),
                              embedded_engine_source_sha256=digest(new_dat.engine),
                              bank_section_unchanged=True))
    save('dat-audit.json',dict(real_packages=results,other_generations=older,mixed_files=mixed,
                              parent_C_gate_entry_point='research/g156/r2_static.py:main',
                              parent_inputs_local=str(original_local),output_only_rebound=True))
    print(json.dumps(dict(status='PASS',round_trips=len(results),bank_negative_cases=60,
                          mixed_accepted=sum(row['studio_accepts'] for row in mixed),mixed_files=mixed),ensure_ascii=False))


if __name__ == '__main__':
    main()
