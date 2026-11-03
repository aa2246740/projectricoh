"""Build generation 132 with the gen 121 envelope and diagnostic-only entries."""
from pathlib import Path
import copy
import json
import shutil
import struct
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / 'research/diag_dat_v21'))
import scope
sys.path.insert(0, str(HERE / 'candidate'))
import common as c
import service_build

GENERATION = 132
BASE = ROOT / 'firmware/package_v36_g121/SD_ROOT/GXRCE.DAT'
BASE_SHA = '3b9342ee28c523d7737e320abac1cc37ee3e6c6d122a72d5fe90cd2a3f2ee131'


def model(pack):
    assert scope.sha(BASE) == BASE_SHA
    raw = BASE.read_bytes()
    modules = []
    shared = pack.u32(raw, 192)
    for mi, name in enumerate(pack.NAMES):
        d = raw[pack.u32(raw, 156) + 64 * mi:pack.u32(raw, 156) + 64 * (mi + 1)]
        mapping = raw[pack.u32(d, 12):pack.u32(d, 12) + 152]
        records = [raw[pack.u32(d, 16) + 32 + 64*i:pack.u32(d, 16) + 96 + 64*i] for i in range(16)]
        table = pack.u32(d, 20)
        entries, owners = {}, []
        for i in range(d[30]):
            desc = raw[table + 16 + 20*i:table + 36 + 20*i]
            slot = desc[0]
            owners.append(slot)
            e = bytearray(552)
            e[:2], e[4:8], e[445:447] = desc[:2], desc[4:8], desc[2:4]
            for off, size, kind, index in zip(pack.OFFSETS, pack.ROW_BYTES, pack.KINDS, desc[8:18]):
                pool = shared + 16 + 12*kind
                assert pack.u16(raw, pool + 2) == size
                at = shared + pack.u32(raw, pool + 4) + index*size
                e[off:off+size] = raw[at:at+size]
            for off, size, crc_off in ((20,62,8),(82,33,12),(115,96,16),(216,56,212),
                                      (284,62,272),(346,33,276),(379,66,280),(456,62,448),(518,33,452)):
                pack.p32(e, crc_off, pack.crc(e[off:off+size]))
            entries[slot] = bytes(e)
        refs, ranges = [], []
        for i in range(16):
            meta = raw[pack.u32(d, 24)+28*i:pack.u32(d, 24)+28*(i+1)]
            refs.append(owners[meta[24]])
            ranges.append([struct.unpack('bbb', meta[3*j:3*j+3]) for j in range(8)])
        stock = entries[4]
        raw_stock = b''.join(stock[off:off+size] for off, size in zip(pack.OFFSETS, pack.ROW_BYTES)) + stock[445:447]
        assert pack.crc(mapping + raw_stock) == pack.u32(d, 32) == pack.PIN_CRC32[mi]
        modules.append(dict(name=name, map=mapping, records=records, entries=entries, refs=refs,
                            ranges=ranges, raw_stock=raw_stock, entry=stock, crc_pin=pack.u32(d,32), pin=d[32:64]))
    return modules


def main():
    scope.freeze_check()
    c.guard()
    pack = c.load(c.PRODUCT / 'pack.py', 'diag_pack')
    build = c.load(c.PRODUCT / 'build.py', 'diag_link')
    modules = model(pack)
    service_build.main()
    inert, _, _ = pack.pack_model(copy.deepcopy(modules), GENERATION)
    # Keep the gen 121 linker, flags, libc, service archive and relocation proof.
    # Recipe, panel and storage product implementations are not linked.
    build.sources = lambda: [(c.PRODUCT / 'diag.c', False),
                            (c.PRODUCT / 'src/firmware/engine/core/eng_mem.c', False)]
    build.LOCAL = c.LOCAL / 'product-r13'
    build.LOCAL.mkdir(exist_ok=True)
    layout = build.build(len(inert) - 256 - len(pack.STUB), lto=True)
    built = build.LOCAL / 'm32r-lto'
    rel = (built / 'reloc.bin').read_bytes()
    identity = json.loads((ROOT / 'firmware/resident_v36/local/resident/trust.json').read_text())
    blob, trust, stats = pack.pack_model(modules, GENERATION, engine=(built/'engine.bin').read_bytes(),
        relocations=[struct.unpack_from('>II', rel, i) for i in range(0, len(rel), 8)],
        bss=layout['bss_bytes'], entry=layout['entries']['ig_bootstrap'],
        resident_id=bytes.fromhex(identity['resident_build_id']), abi_id=bytes.fromhex(identity['resident_abi_id']))
    # The resident trusts the official body identity, as in gen 121. The
    # patched ilaunch3 artifact has a different whole-file SHA256.
    assert blob[48:112] == BASE.read_bytes()[48:112]
    assert len(blob) == layout['file_bytes'] <= 65536
    out = c.LOCAL / 'full-r13'
    out.mkdir(exist_ok=True)
    for name in ('engine.bin', 'engine.elf', 'engine.map', 'reloc.bin'):
        shutil.copyfile(built / name, out / name)
    (out / 'GXRCE.DAT').write_bytes(blob)
    scope.save(out / 'layout.json', layout)
    scope.save(out / 'manifest.json', dict(status='BUILT_HOST_ONLY', generation=GENERATION,
        sha256=scope.sha(out/'GXRCE.DAT'), baseline_sha256=BASE_SHA, camera_acceptance=False,
        resident_build_id=identity['resident_build_id'], resident_abi_id=identity['resident_abi_id'], **stats))
    print('BUILT', GENERATION, len(blob), scope.sha(out / 'GXRCE.DAT'), flush=True)


if __name__ == '__main__':
    main()
