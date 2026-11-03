#!/usr/bin/python3
"""Prepare a supported non-04 settings selector, preserving the valid record."""
import hashlib
import json
import os
from pathlib import Path
import struct
import zlib

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def main():
    assert os.getpriority(os.PRIO_PROCESS, 0) >= 10
    source = ROOT / 'research/v310_body/fix/local/mount-look-settings.bin'
    original = source.read_bytes()
    assert len(original) == 4096 and original[0x36e] == 1
    record = original[0xfd4:0xffc]
    assert zlib.crc32(record[:36]) == int.from_bytes(record[-4:], 'big')
    data = bytearray(original)
    data[0x36e] = 3
    struct.pack_into('>I', data, 0xffc, sum(struct.unpack('>2046H', data[:0xffc])) & 0xffffffff)
    target = HERE / 'local/non-pure03-settings.bin'
    assert not target.exists()
    target.write_bytes(data)
    receipt = dict(source=str(source.relative_to(ROOT)), source_sha256=hashlib.sha256(original).hexdigest(),
        output=str(target.relative_to(ROOT)), sha256=hashlib.sha256(data).hexdigest(),
        selector_change=[1, 3], record_preserved=True, valid_record_CRC=True,
        mode_parameters={'0x645': data[0x645], '0x646': data[0x646]},
        source_kind='Declared persistent settings; supported selector 3, not a direct native state assignment',
        earlier_selector_2='Invalid target for this test: actual MAIN cold startup normalizes selector 2 to 1 before BOOT')
    (HERE / 'evidence/non-pure03-input.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt))


if __name__ == '__main__':
    main()
