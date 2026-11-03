#!/usr/bin/python3 -I -B
"""Bind report locations to original file offsets and focused local excerpts."""
import importlib.util
import json
from pathlib import Path
import struct

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('xpan_readers', HERE / 'inspect.py')
readers = importlib.util.module_from_spec(spec)
spec.loader.exec_module(readers)

SITES = {
    'jlaunch3': {
        'aspect': (0x2019a4c8, 0x2019a4f4),
        'dimensions': (0x2019a9f4, 0x2019ae78),
        'size_constants': (0x201a2c68, 0x201a300c),
        'raw_rectangle': (0x2018b61c, 0x2018b824),
        'raw_margin': (0x201a10a4, 0x201a10e0),
        'jpeg_rectangle': (0x2018646c, 0x20186830),
        'output_config': (0x2019fc5c, 0x2019fe48),
        'dng_dimensions': (0x2019d2c0, 0x2019d330),
        'dng_call': (0x20198ecc, 0x20198fc0),
        'dng_writer': (0x2015fcdc, 0x2015fd68),
        'dng_raw_size': (0x2016178c, 0x2016183c),
        'dng_crop': (0x20161ecc, 0x20162100),
        'display': (0x201255d0, 0x201258b4),
        'native_flag': (0x201839d4, 0x201839e8),
        'display_registers': (0x20254a20, 0x20254c40),
        'display_constants': (0x2013d9bc, 0x2013d9d4),
        'checksum': (0x200759ec, 0x20075a10),
        'file_checks': (0x2007a6a8, 0x2007ad38),
        'storage_ranges': (0x20077a84, 0x20077bf4),
        'storage_writer': (0x2007bcb0, 0x2007c000),
        'update_loop': (0x2007c630, 0x2007c800),
    },
    'qlaunch3': {
        'aspect': (0x2019d8c8, 0x2019d8f4),
        'dimensions': (0x2019ddf4, 0x2019e278),
        'size_constants': (0x201a609c, 0x201a6440),
        'raw_rectangle': (0x2018ea1c, 0x2018ec24),
        'raw_margin': (0x201a44d8, 0x201a4514),
        'jpeg_rectangle': (0x2018986c, 0x20189c30),
        'output_config': (0x201a3090, 0x201a327c),
        'dng_dimensions': (0x201a06c0, 0x201a0730),
        'dng_call': (0x2019c2cc, 0x2019c3c0),
        'dng_writer': (0x201630dc, 0x20163168),
        'dng_crop': (0x201652cc, 0x20165500),
        'display': (0x20128214, 0x201284f8),
        'native_flag': (0x20186dd4, 0x20186de8),
        'display_registers': (0x20258220, 0x20258440),
        'display_constants': (0x20140c50, 0x20140c68),
        'checksum': (0x200759ec, 0x20075a10),
        'file_checks': (0x2007a6a8, 0x2007ad38),
        'storage_writer': (0x2007bcb0, 0x2007c000),
        'update_loop': (0x2007c630, 0x2007c800),
    },
    'l08firm3': {
        'aspect': (0x20199cbc, 0x20199ce8),
        'dimensions': (0x2019a1f0, 0x2019a674),
        'size_constants': (0x201a249c, 0x201a2840),
        'raw_rectangle': (0x2018acb0, 0x2018aeb8),
        'raw_margin': (0x201a08d8, 0x201a0914),
        'jpeg_rectangle': (0x20185aec, 0x20185eb0),
        'output_config': (0x2019f490, 0x2019f67c),
        'dng_dimensions': (0x2019cabc, 0x2019cb2c),
        'dng_call': (0x201985bc, 0x201986b0),
        'dng_writer': (0x2015f0dc, 0x2015f168),
        'dng_crop': (0x201612cc, 0x20161500),
        'display': (0x2012016c, 0x20120450),
        'native_flag': (0x20182dd4, 0x20182de8),
        'display_registers': (0x20253620, 0x20253840),
        'display_constants': (0x2013bd60, 0x2013bd78),
        'checksum': (0x200759f0, 0x20075a14),
        'file_checks': (0x2007b1ac, 0x2007b83c),
        'storage_writer': (0x2007c7b4, 0x2007cb04),
        'update_loop': (0x2007d134, 0x2007d304),
    },
    'ilaunch3': {
        'body_update': (0x2036d4e8, 0x2036db00),
        'unit_update': (0x2036fac8, 0x2036fbe4),
        'body_start': (0x2005c538, 0x2005c6d0),
        'checksum': (0x20087af0, 0x20087b14),
        'playback_entry': (0x2018d6d4, 0x2018d74c),
    },
}

LITERALS = {
    'jlaunch3': (0x201a2ed8, 0x201a2ee8, 0x201a2fd8, 0x201a2fe4, 0x201a2f50, 0x201a2f60),
    'qlaunch3': (0x201a630c, 0x201a631c, 0x201a640c, 0x201a6418, 0x201a6384, 0x201a6394),
    'l08firm3': (0x201a270c, 0x201a271c, 0x201a280c, 0x201a2818, 0x201a2784, 0x201a2794),
}


def main():
    result = {}
    changes = {}
    for name, sites in SITES.items():
        data = readers.read(name)
        out = {}
        rows = list(readers.lines(name))
        for label, (start, end) in sites.items():
            off = readers.mapping(data, start, True)
            final = readers.mapping(data, end-1, True)
            assert off is not None and final == off+end-start-1
            out[label] = dict(vma=hex(start), end=hex(end), file=hex(off),
                              bytes=end-start, sha256=readers.digest(data[off:final+1]))
            if label == 'display_constants':
                values = [struct.unpack_from('>d', data, off+i)[0] for i in (0, 8, 16)]
                assert values == [2, 54, 64]
                out[label]['values'] = values
            listing = [f'{name} {label} {hex(start)} {hex(end)} file {hex(off)}',
                       'SHA256 ' + readers.digest(data), 'Static listing only.']
            listing.extend(x[4] for x in rows if start <= x[0] < end)
            readers.put(readers.LOCAL / 'evidence' / f'{name}-{label}.txt', '\n'.join(listing)+'\n')
        if name in LITERALS:
            literals = []
            proposed = []
            for label, address in zip(('L_width_16', 'L_height_16', 'L_x_store_16',
                                       'L_y_16', 'M_width_16', 'M_height_16'), LITERALS[name]):
                off = readers.mapping(data, address, True)
                literals.append(dict(field=label, vma=hex(address), file=hex(off),
                                     original=data[off:off+4].hex()))
                values = dict(L_width_16=4160, L_height_16=1536,
                              L_x_store_16=64, L_y_16=656,
                              M_width_16=3120, M_height_16=1152)
                entry = dict(field=label, vma=hex(address), file=hex(off),
                             proposed_value=values[label])
                if label != 'L_x_store_16':
                    entry.update(value_file=hex(off+2), original_value=data[off+2:off+4].hex(),
                                 proposed_bytes=struct.pack('>H', values[label]).hex())
                else:
                    entry['note'] = 'The existing store shares a zero value. A separate instruction is required.'
                proposed.append(entry)
            out['constant_sites'] = literals
            changes[name] = dict(state='INCOMPLETE', entries=proposed,
                                 remaining=['Display horizontal limits', 'Display vertical limits',
                                            'Other size cases and recording modes',
                                            'JPEG encoder and playback acceptance',
                                            'Final file checksum'])
        result[name] = out
    for name, va in [('jlaunch0', 0x27e3553c), ('qlaunch0', 0x27e3553c),
                     ('l08firm0', 0x27e35540)]:
        data = readers.read(name)
        off = readers.mapping(data, va, True)
        result[name] = dict(checksum_vma=hex(va), file=hex(off),
                            sha256=readers.digest(data),
                            checksum_code_sha256=readers.digest(data[off:off+36]))
    readers.put(readers.LOCAL / 'locations.json', json.dumps(result, indent=2)+'\n')
    readers.put(readers.LOCAL / 'change-sites.json', json.dumps(changes, indent=2)+'\n')
    print('Mapped image sets', len(result))
    for name in LITERALS:
        print(name, 'dimension', result[name]['dimensions']['file'],
              'initializer', result[name]['size_constants']['file'],
              'display', result[name]['display']['file'])


if __name__ == '__main__':
    main()
