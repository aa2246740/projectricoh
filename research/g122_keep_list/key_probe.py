"""Read the original raw-key conversion and native dispatch results."""
from pathlib import Path
import argparse
import struct
import sys
import traceback
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ROOT, OUT, load, save
ux = load(OUT / 'native_ux.py', 'native_ux')
m, fr, pe, v = ux.m, ux.fr, ux.pe, ux.v

def configure(baseline=True):
    dat, elf = ux.configure(False, 'keys')
    if baseline:
        dat = ROOT / 'firmware/package_v36_g120b/SD_ROOT/GXRCE.DAT'
        elf = ROOT / 'firmware/engine_v42_ux/candidate/local/full-r13/engine.elf'
    m.DAT = dat
    pe.STAGED, pe.STAGED_SHA, pe.ENGINE_ELF = dat, m.sha(dat.read_bytes()), elf
    v.python_backend.CACHE = OUT / 'decode/keys'
    from runtime_guard import install
    install(v)
    original = m.Product.symbol_pc
    if not getattr(m.Product, 'field_alias', False):
        def resolved(self, name):
            actual = next((x for x in (name,name+'.constprop.0',name+'.lto_priv.0') if x in self.elf.symbols),name)
            return original(self, actual)
        m.Product.symbol_pc = resolved
        m.Product.field_alias = True
    return dat, elf

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--final', action='store_true')
    args = parser.parse_args()
    dat, elf = configure(not args.final)
    h, p, w = m.boot('50mm')
    m.published(h, p, w)
    h.select_item_8()
    h.b.map(0x20690000, bytes(512))
    report = dict(dat_sha256=m.sha(dat.read_bytes()), conversion=[], raw=[], keys=[], boundaries=[])
    for key in range(1, 0x80):
        result = fr.native(h, 0x20289a9c, (key,))
        assert result['ok'], result
        report['conversion'].append(dict(logical=key, ui=result['r0']))
    def record(b):
        report['boundaries'].append(dict(pc=hex(b.pc), args=list(b.core.r[4:8])))
        return False
    for address in (0x202741a8, 0x202741c0, 0x20272ed8, 0x2026a2f8):
        h.b.breakpoints.setdefault(address, []).insert(0, record)
    for raw, phase in [(0x0d, 1), (0x0e, 1), (0x0f, 1), (0x10, 1), (0x12, 1),
                       (0x11, 1), (0x13, 1), (0x14, 1), (0x18, 1), (0x20, 1),
                       (0x1f, 1), (0x21, 1), (0x22, 1)]:
        message = bytearray(140)
        struct.pack_into('>H', message, 6, 0x700b)
        struct.pack_into('>II', message, 12, raw, phase)
        h.b.origin = 'model:key_message'
        h.b.write(0x20690000, message)
        result = fr.native(h, 0x202afe98, (0x20690000,), steps=200000)
        report['raw'].append(dict(raw=raw, phase=phase, result=result))
        if not result['ok']:
            break
    save('key-probe.json', report)
    print('PASS key conversion; raw results', report['raw'], flush=True)

if __name__ == '__main__':
    main()
