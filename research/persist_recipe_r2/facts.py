"""Check fixed DAT records and each unit's initialized row spans."""
import hashlib
import json
from pathlib import Path
import struct
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import study


class UnitImage:
    def __init__(self, name):
        self.path = study.ROOT / 'artifacts/firmware/gxr-1.51' / name
        self.data = self.path.read_bytes()
        expected = {
            'jlaunch3':'951be1c659c85af58ae3e4ce98707c52f0b4514fc2075256854d59f822671673',
            'qlaunch3':'e487d00b5539aa1e3ca9373829456e00676b37310dc717f0a5bcb5235bac6690',
            'l08firm3':'0a4dff6d3be9b9a9b56dfcbd98a2df59efcb31f7d4eaca6b0c3fbdb1641fde44',
        }
        assert hashlib.sha256(self.data).hexdigest()==expected[name]
        self.sections = []
        for index in range(16):
            src, address, length, zero, count = struct.unpack_from('>5I', self.data, 32+20*index)
            self.sections.append(dict(index=index, file=512+src, address=address,
                                      size=length, zero=zero, zero_size=count))

    def offset(self, address, count):
        found = [row for row in self.sections if row['address'] <= address
                 and address+count <= row['address']+row['size']]
        assert len(found) == 1, hex(address)
        row = found[0]
        return row['file']+address-row['address'], row['index']

    def raw(self, address, count):
        at, _ = self.offset(address, count)
        return self.data[at:at+count]


def main():
    data = (study.ROOT/'firmware/package_v37_g135/local/SD_ROOT/GXRCE.DAT').read_bytes()
    assert hashlib.sha256(data).hexdigest() == '57743bc105bc3d51b7fa65b44efd90afb022b2356d4e7846d470cc0c641c438a'
    sections = [struct.unpack_from('>HHII', data, 128+12*i) for i in range(7)]
    modules = []
    labels = ('a5', 'b5', 'colour', 'matrix', 'a20', 'b20', 'cd', 'a14', 'b14')
    for module in range(3):
        directory = sections[2][2]+64*module
        name = data[directory:directory+8].split(b'\0')[0].decode()
        im = UnitImage(name+'3')
        mapping, bank, table = struct.unpack_from('>III', data, directory+12)
        desc = data[table+16:table+36]
        shared = sections[5][2]
        decoded = []
        for item, kind in enumerate((0,1,2,3,0,1,1,1,0,1)):
            count, length, at = struct.unpack_from('>HHI',data,shared+16+12*kind)
            assert desc[8+item]<count
            at += shared+desc[8+item]*length
            decoded.append(data[at:at+length])
        stock_rows = decoded[:6]+[decoded[6]+decoded[7]]+decoded[8:]
        records = []
        for slot in range(1, 9):
            at = bank+32+64*(slot-1)
            row = data[at:at+64]
            records.append(dict(slot=slot, enabled=row[1], mode=row[3],
                                wb_signed=list(struct.unpack('bb', row[49:51])),
                                plan_offsets=['0x36e','0x6dd','0x6de']))
        assert all(row['mode'] == 1 and row['wb_signed'] == [0,0] for row in records)
        rows = []
        for index, label in enumerate(labels):
            address, count, entry_at, flag, extra = struct.unpack_from('>IHHHH', data, mapping+32+12*index)
            at, section = im.offset(address, count)
            raw = im.data[at:at+count]
            assert raw==stock_rows[index]
            rows.append(dict(name=label, address=hex(address), size=count,
                             entry_offset=entry_at, section=section, file=hex(at),
                             sha256=hashlib.sha256(raw).hexdigest(),
                             raw_equals_dat_stock=True))
        pointer_at = 0x200b4280 if module == 2 else 0x200b2cf0
        pointer = int.from_bytes(im.raw(pointer_at, 4), 'big')
        default_at = (0x6d3d4, 0x6d3fc, 0x6e98c)[module]
        modules.append(dict(name=name, firmware_sha256=study.sha(im.path), records=records,
                            rows=rows, initialized_sections=im.sections,
                            t_pointer=hex(pointer_at), initial_t_ram=hex(pointer),
                            t_default_file=hex(default_at),
                            t_default_control=im.data[default_at+0x2444:default_at+0x2446].hex()))
    assert all(row['t_default_control']=='0002' for row in modules)
    study.save('dat-unit-facts.json', dict(dat_sha256=hashlib.sha256(data).hexdigest(),
               modules=modules, all_24_plans_standard_neutral=True,
               limits='File initialization and embedded defaults, not a live boot or stored calibration image.'))
    targets = {hex(item) for item in (0x20067bb4, 0x2006a050, 0x2006a0f4,
               0x20060b84, 0x20060bb4, 0x20060c10, 0x20067b2c)}
    calls = json.loads((study.ROOT/'research/persist_recipe/local/calls.json').read_text())
    selected = [row for row in calls if row.get('target') in targets]
    study.save('selected-calls.json', selected)
    print(json.dumps(dict(modules=len(modules), plans=24, rows=27,
                          all_plans_equal=True, selected_calls=len(selected))))


if __name__ == '__main__':
    main()
