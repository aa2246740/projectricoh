"""Map original MY record copies using synthetic records and RAM-only file models."""
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import collect
from replay import Rig, S


def run(target, phase):
    r = Rig()
    try:
        r.valid_s()
        r.cpu.write(S+16, bytes([165])*4076)
        touched = set()
        def written(address, data):
            touched.update(range(address-S, address-S+len(data)))
        r.cpu.add_write_trace(S, S+4096, written)
        record = bytearray((i & 255 if phase == 0 else i >> 8 if phase == 1
                            else (i*37+11) & 255) for i in range(1024))
        address = 0x20620000
        r.cpu.write(address, record)
        value = r.call(0x2011d700, (address, 256, 543))
        record[0x50:0x54] = value.to_bytes(4, 'big')
        def read_record(args):
            assert args[0] == 129 and args[2] == 1024
            r.cpu.write(args[1], record)
        r.stub(0x200a3228, 1, 'medium_available_model')
        r.stub(0x200a40b4, 129, 'open_record_model')
        r.stub(0x200a449c, 1024, 'read_record_model', read_record)
        r.stub(0x200a437c, 0, 'close_record_model')
        r.stub(0x2012097c, 0, 'record_status_model')
        result = r.call(0x2011e350, (1, target))
        assert result == 0
        assert not any(e['name']=='record_status_model' and e['args'][0] for e in r.events)
        return r.cpu.read(S, 4096), touched
    finally:
        r.close()


def main():
    collect.preflight()
    results = []
    for target in (1, 2, 3):
        runs = [run(target, phase) for phase in range(3)]
        touched = set.union(*(r[1] for r in runs))
        mapping = []
        for destination in sorted(touched):
            source = runs[0][0][destination]+256*runs[1][0][destination]
            exact = source < 1024 and runs[2][0][destination] == (source*37+11) & 255
            mapping.append(dict(s_offset=hex(destination),
                                record_offset=hex(source) if exact else None))
        result = dict(target=target, writes=len(touched), tail_touched=any(0xfd4<=n<0xffc for n in touched),
                      mapping=mapping)
        results.append(result)
        selected = {'0x104','0x105','0x106','0x107','0x108','0x109','0x10a',
                    '0x143','0x144','0x152','0x157','0x15c','0x161'}
        print(json.dumps(dict(target=target, writes=len(touched), tail_touched=result['tail_touched'],
                              copies=[m for m in mapping if m['record_offset'] in selected])))
    collect.save('my-slot-mapping.json', dict(status='PASS_FUNCTION_REPLAY', results=results,
        original_sha256=collect.EXPECTED,
        library_sha256=collect.sha(collect.ROOT/'tools/gxr_emulator/build/libgxr_m32r.dylib'),
        source_hashes={str(p.relative_to(collect.ROOT)): collect.sha(p) for p in
            (HERE/'my_slots.py', HERE/'replay.py', HERE/'collect.py', collect.ROOT/'tools/gxr_emulator/backend.py')},
        limits='Original card-import function, synthetic records, modeled open/read/close. No user settings, media, UI recall, whole boot or native storage acceptance.'))


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        collect.OUT.mkdir(exist_ok=True)
        collect.save('my-slot-failure.json', dict(error=repr(exc)))
        print(type(exc).__name__+': see local/my-slot-failure.json')
        raise SystemExit(1)
