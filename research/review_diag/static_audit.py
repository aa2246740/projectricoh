"""Bind source, data, instructions and bounded machine-code spans to gen 125."""
from pathlib import Path
from collections import Counter
import difflib
import hashlib
import importlib.util
import json
import re
import struct
import subprocess

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
ENGINE = ROOT / 'firmware/engine_diag_v1'
COMPILED = ENGINE / 'candidate/local/full-r13'
DAT = ROOT / 'firmware/package_v36_diag1/local/SD_ROOT/GXRCE.DAT'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    spec = importlib.util.spec_from_file_location('review_elf_reader', ROOT / 'firmware/stage2l_switch/tools/build.py')
    reader = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(reader)
    elf = reader.Elf(COMPILED / 'engine.elf')
    raw = DAT.read_bytes()
    section = next(s for s in elf.sections if s['name'] == '.engine')
    engine = elf.content(section)
    assert len(raw) == 19288 and int.from_bytes(raw[28:32], 'big') == 125
    assert raw == (COMPILED / 'GXRCE.DAT').read_bytes()
    assert engine == (COMPILED / 'engine.bin').read_bytes() == raw[256:256+len(engine)]
    assert sha(DAT) == '38e3db6eacaf05a4ad8dbafbda608e3b5695485110014f7816f32d315b3f49a1'
    tool = ROOT / 'research/tooling_m32r/prefix/bin/m32r-elf-objdump'
    argv = [str(tool), '-d', '-z', str(COMPILED / 'engine.elf')]
    text = subprocess.run(argv, capture_output=True, text=True, check=True).stdout
    (OUT / 'local/final-dat-disassembly.txt').write_text(text)
    instructions = []
    for line in text.splitlines():
        match = re.match(r'^\s*([0-9a-f]+):\s+((?:[0-9a-f]{2}\s+)+)\s*(.*)$', line)
        if match:
            instructions.append(dict(address=int(match[1],16), bytes=len(match[2].split()), asm=match[3], line=line))
    functions = {n:s for n,s in elf.symbols.items() if s['info'] & 15 == 2 and s['size']}
    compiled = {}
    (OUT / 'local/compiled').mkdir(exist_ok=True)
    direct_calls = []
    for name, symbol in functions.items():
        lo, hi = symbol['value'], symbol['value'] + symbol['size']
        lines = [i for i in instructions if lo <= i['address'] < hi]
        covered = {a for i in lines for a in range(i['address'], min(i['address']+i['bytes'],hi))}
        anomalies = [i['line'] for i in lines if any(s in i['asm'] for s in ('.word','.short','(bad)','unknown'))]
        assert len(covered) == symbol['size'], (name, len(covered), symbol['size'])
        assert not anomalies, (name, anomalies)
        listing = '\n'.join(i['line'] for i in lines) + '\n'
        (OUT / 'local/compiled' / (name + '.txt')).write_text(listing)
        calls = []
        for instruction in lines:
            for target in re.findall(r'\bbl\s+([0-9a-f]+)\s+<', instruction['asm']):
                target = int(target,16)
                if not lo <= target < hi:
                    target_name = next((n for n,s in elf.symbols.items() if s['value'] == target and
                        (s['info'] & 15 == 2 or n.startswith('rv_'))), hex(target))
                    calls.append(target_name)
                    direct_calls.append(dict(source=name, pc=hex(instruction['address']), target=target_name))
        compiled[name] = dict(address=hex(lo), bytes=symbol['size'], end=hex(hi),
            decoded_bytes=len(covered), anomalies=anomalies, direct_callees=sorted(set(calls)))
    bridge_source = (ENGINE / 'candidate/engine_services/bridges.S').read_text()
    bridges = {}
    for name, address in re.findall(r'^\s+NATIVE (\w+),(0x[0-9a-f]+)', bridge_source,re.M):
        offset = elf.symbols[name]['value']
        stub = raw[offset:offset+8]
        assert stub[:2] == bytes.fromhex('d6c0') and stub[4:6] == bytes.fromhex('86e6')
        target = int.from_bytes(stub[2:4],'big') << 16 | int.from_bytes(stub[6:8],'big')
        assert target == int(address,16)
        bridges[name] = dict(address=hex(offset), target=hex(target),
            C_callers=sorted({c['source'] for c in direct_calls if c['target']==name}))
    used_bridges = {name for name,x in bridges.items() if x['C_callers']}
    assert used_bridges == {'rv_native_context','rv_native_ascii','rv_native_language','rv_native_draw'}
    assert not any(c['target']=='rv_rpc8_native' for c in direct_calls)
    indirect = [i for i in instructions if i['address'] < 0x22e0 and re.search(r'\bjl\b',i['asm'])]
    assert {i['address'] for i in indirect} == {0x194,0x226c,0x22a0}
    api = elf.symbols['rv_api']['value']
    assert int.from_bytes(raw[api+16:api+20],'big') == elf.symbols['rv_call']['value']
    layout = json.loads((ROOT / 'research/diag_dat_v1/layout.json').read_text())
    fields_at = elf.symbols['diag_fields']['value']
    fields = {}
    for index,name in enumerate(layout['field_order']):
        address,width = struct.unpack_from('>IB', raw, fields_at+index*8)
        assert [hex(address),width] == layout['fields'][name]
        assert width in (1,2,4) and address % width == 0
        fields[name] = [hex(address),width]
    original_spec = json.loads((ROOT / 'research/body_v4_storage/validation/diagnostic_spec.json').read_text())
    assert all(fields[name] == pair for name,pair in original_spec['fields'].items())
    cells_at = elf.symbols['diag_layout']['value']
    used = []
    for page,rows in enumerate(layout['pages'].values()):
        assert len(rows) == 7
        for row, names in enumerate(rows):
            expected = [(255,4) if n=='open_high' else (layout['field_order'].index(n),fields[n][1]*2) for n in names]
            actual = [struct.unpack_from('BB',raw,cells_at+2*(page*28+row*4+i)) for i in range(4)]
            assert actual == expected + [(0,0)]*(4-len(expected)), (page,row)
            assert sum(x[1] for x in actual) <= 8
            used.extend(n for n in names if n!='open_high')
    assert Counter(used) == Counter(fields.keys())
    changes = []
    for relative in ('candidate/containers/product/diag.c','candidate/engine_services/native_seed.c','candidate/engine_services/services.c'):
        new = (ENGINE / relative).read_text()
        old_path = ROOT / 'firmware/engine_v43_fix' / relative
        old = old_path.read_text() if old_path.exists() else ''
        changes.append(''.join(difflib.unified_diff(old.splitlines(True),new.splitlines(True),fromfile='gen121/'+relative,tofile='diag125/'+relative)))
    (OUT / 'local/source-delta.patch').write_text('\n'.join(changes))
    stack = {}
    for line in (ENGINE / 'candidate/local/product-r13/m32r-lto/engine.elf.ltrans0.ltrans.su').read_text().splitlines():
        location, amount, kind = line.split('\t')
        stack[location.rsplit(':',1)[-1]] = dict(bytes=int(amount),kind=kind)
    assert all(x['kind'] == 'static' for x in stack.values())
    base = json.loads((COMPILED / 'layout.json').read_text())
    assert all(sha(ROOT / path) == digest for path,digest in base['sources'].items())
    assert all(sha(ROOT / path) == digest for path,digest in base['tools'].items())
    result = dict(status='PASS_DAT_INTRINSIC_STATIC_BOUNDARY', dat_sha256=sha(DAT),
        elf_sha256=sha(COMPILED / 'engine.elf'), instructions_command=argv,
        dat_engine_elf_equal=True, compiled_functions=compiled, bridges=bridges,
        direct_calls=direct_calls, indirect_calls=[dict(pc=hex(i['address']),asm=i['asm']) for i in indirect],
        call_api_target='rv_call', no_direct_file_or_rpc_call=True, fields=fields,
        file_bytes=len(raw), code_and_constants_bytes=len(engine), bss_bytes=base['bss_bytes'],
        stack=stack, maximum_static_C_frame=max(x['bytes'] for x in stack.values()),
        original_resident_header_equal=(ENGINE / 'resident/resident.h').read_bytes()==(ROOT / 'firmware/resident_v36/resident/resident.h').read_bytes(),
        limits='This verifies the DAT and its own dispatch graph. Nested original handlers are tested separately; the prepublication setter counterexample prevents a global read-only verdict.')
    (OUT / 'evidence/static-audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print('PASS',len(compiled),'compiled C spans; max C frame',result['maximum_static_C_frame'],'bytes; 50 compiled fields and 5 layouts; four reachable native bridges')


if __name__ == '__main__':
    main()
