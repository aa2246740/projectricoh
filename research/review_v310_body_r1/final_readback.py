#!/usr/bin/python3
"""Rebuild MAIN solely from NAND pages produced by independent recovery runs."""
import hashlib
import json
import os
from pathlib import Path
import struct
import sys
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
from audit import memory, snapshot


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    assert os.getpriority(os.PRIO_PROCESS, 0) >= 10
    target = HERE / 'evidence/independent-recovery-readback.json'
    assert not target.exists()
    with zipfile.ZipFile(ROOT / 'artifacts/downloads/gxr-151.zip') as archive:
        official = next(archive.read(i) for i in archive.infolist() if Path(i.filename).name == 'ilaunch3')
    rows = []
    for flow in ('official', 'v310'):
        name = flow + '-tail-exact-up-batch'
        receipt = json.loads((HERE / 'evidence' / (name + '.json')).read_text())
        assert receipt['status'] == 'PASS' and receipt['backend'] == 'original-batch'
        source = ROOT / receipt['final_snapshot']
        assert sha(source.read_bytes()) == receipt['final_snapshot_sha256']
        state = snapshot(source)['cpu']
        nand = next(d for t, d in zip(state['device_types'], state['devices']) if t in ('NAND', 'WordColumnNAND'))
        u = lambda at: int.from_bytes(memory(state, at, 4), 'big')
        remaps = []
        for i in range(30):
            stamp, old, new = struct.unpack('>IHH', memory(state, 0x204c40ec + 8 * i, 8))
            if stamp == 0xffffffff:
                break
            remaps.append((old, new, stamp))
        def physical(block):
            seen = set()
            while True:
                assert block not in seen
                seen.add(block)
                matches = [v for v in remaps if v[0] == block]
                if not matches:
                    return block
                assert len(matches) == 1
                block = matches[0][1]
        def sector(lba):
            block, index = divmod(lba, 256)
            page, part = divmod(physical(block) * 256 + index, 4)
            raw = nand['pages'].get(page, b'\xff' * 2112)
            return bytes(raw[part * 512:(part + 1) * 512])
        first = u(0x200c0d54) + 35
        last = first + u(0x200c0d50) - 1
        tail = u(0x200c0d60)
        header = sector(last * 256 + tail)
        length = int.from_bytes(header[0x168:0x16c], 'big')
        assert length == 3993340 and header[16] == 2
        actual = header + b''.join(sector(first * 256 + i) for i in range((length - 512 + 511) // 512))[:length - 512]
        assert actual == official
        output = HERE / 'local' / ('independently-recovered-' + flow + '-ilaunch3')
        assert not output.exists()
        output.write_bytes(actual)
        json_path = HERE / 'local' / (name + '-nand.json')
        serialized = {int(k): bytes.fromhex(v) for k, v in json.loads(json_path.read_text()).items()}
        assert serialized == {int(k): bytes(v) for k, v in nand['pages'].items()}
        cold = json.loads((HERE / 'evidence' / ('recovered-' + flow + '-batch.json')).read_text())
        cold_seed = {int(k): bytes.fromhex(v) for k, v in json.loads((ROOT / cold['NAND_source']).read_text()).items()}
        assert serialized == cold_seed
        assert (ROOT / cold['image']).read_bytes() == actual
        assert cold['status'] == 'PASS' and cold['backend'] == 'original-batch'
        assert [v['state'] for v in cold['state_sequence']] == [0, 2, 32, 5]
        T = b''.join(bytes(nand['pages'].get(2624 + i, b'\xff' * 2112)[:2048]) for i in range(8))
        assert sha(T) == cold['T_sha256'] and cold['T_equal_persisted_NAND']
        rows.append(dict(flow=flow, source=str(source.relative_to(ROOT)),
            source_sha256=sha(source.read_bytes()), complete_step=receipt['steps'],
            MAIN_bytes=len(actual), MAIN_sha256=sha(actual), MAIN_equal=True,
            NAND_pages=len(serialized), final_NAND_sha256=sha(json_path.read_bytes()),
            T_sha256=sha(T), T_checksum=int.from_bytes(T[-4:], 'big'),
            independent_cold_receipt='evidence/recovered-' + flow + '-batch.json',
            independent_cold_seed_all_pages_equal=True, cold_state_sequence=[0, 2, 32, 5],
            source_regions_used_only_for_layout_and_remap=True,
            official_bytes_used_only_for_comparison=True, native_RAM_changes=[], native_register_changes=[]))
    result = dict(status='PASS', flows=rows, runner_sha256=sha(Path(__file__).read_bytes()),
        scope='Independent exact-input recovery tails plus byte-identical full NAND and new-instance cold starts; the retained 0-to-7B batch prefixes were audited rather than independently replayed')
    target.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(dict(status='PASS', flows=len(rows), MAIN_sha256=sha(official))))


if __name__ == '__main__':
    main()
