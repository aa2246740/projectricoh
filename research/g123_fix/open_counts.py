"""Measure cold and repeated menu RPC counts on the selected DAT."""
from pathlib import Path
import argparse
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_native as n
from common import ROOT, OUT, save, sha, command_lock

def run(unit, generation):
    n.ux.configure(False, unit + '-open-counts')
    from runtime_guard import install
    install(n.v)
    dat = ROOT / ('firmware/package_v36_g121/SD_ROOT/GXRCE.DAT' if generation == 121 else
                  'firmware/package_v36_g123/SD_ROOT/GXRCE.DAT')
    elf = ROOT / ('firmware/engine_v43_fix/candidate/local/full-r13/engine.elf' if generation == 121 else
                  'firmware/engine_v45_verify/candidate/local/full-r13/engine.elf')
    lock = command_lock('open-counts-' + str(generation) + '-' + unit)
    prior = OUT / ('open-counts-' + str(generation) + '-' + unit + '.json')
    if prior.exists():
        record = __import__('json').loads(prior.read_text())
        if record.get('status') == 'PASS' and record.get('dat_sha256') == sha(dat.read_bytes()) and record.get('elf_sha256') == sha(elf.read_bytes()):
            print('PASS existing open counts', generation, unit, 'fixed DAT and ELF', flush=True)
            return
    n.m.DAT = dat
    n.pe.STAGED, n.pe.STAGED_SHA, n.pe.ENGINE_ELF = dat, sha(dat.read_bytes()), elf
    n.v.python_backend.CACHE = OUT / 'decode' / ('open-' + str(generation) + '-' + unit)
    original_symbol = n.m.Product.symbol_pc
    def resolved_symbol(self, name):
        actual = next((x for x in (name, name + '.constprop.0', name + '.lto_priv.0')
                       if x in self.elf.symbols), name)
        return original_symbol(self, actual)
    n.m.Product.symbol_pc = resolved_symbol
    h, p, w = n.m.boot(unit)
    steps = []
    def measure(name, action):
        at = len(p.rpc.log)
        action()
        calls = p.rpc.log[at:]
        row = dict(operation=name, RPC=len(calls), W=sum(x['cmd'] == 22 for x in calls),
                   rpc_log=calls, after=n.ux.snap(h, p))
        if generation == 123 and name in ('reopen_recipe', 'reopen_same_recipe'):
            assert len(calls) == 20 and row['W'] == 0
            directory = int.from_bytes(p.dat[156:160], 'big') + 64 * n.m.INDEX[unit]
            at_map = int.from_bytes(p.dat[directory + 12:directory + 16], 'big')
            mapping = p.dat[at_map:at_map + 152]
            sentinels = []
            assert calls[0]['cmd'] == 23 and calls[1]['cmd'] == 21
            for index in range(9):
                descriptor = mapping[32 + 12 * index:44 + 12 * index]
                base = int.from_bytes(descriptor[:4], 'big')
                size = int.from_bytes(descriptor[4:6], 'big')
                page, read = calls[2 + 2 * index:4 + 2 * index]
                assert page['cmd'] == 23 and read['cmd'] == 21
                address = (page['value'] << 16) | read['value']
                assert address % 2 == 0 and base <= address and address + 2 <= base + size
                sentinels.append(dict(row=index, address=hex(address), bytes=2,
                                      mapped_base=hex(base), mapped_bytes=size, value=read['result']))
            row['contained_sentinel_reads'] = sentinels
        steps.append(row)
    measure('cold', lambda: n.m.published(h, p, w))
    n.ux.need(n.fr.move_key(h, 0x20))
    n.ux.matches(h, p, 5)
    n.ux.need(n.fr.press(h, 0x2b))
    measure('reopen_recipe', lambda: n.m.reopen(h, p, w))
    measure('reopen_same_recipe', lambda: n.m.reopen(h, p, w))
    p.rpc.overlay.clear()
    p.rpc.t = 2
    measure('reopen_after_row_reset', lambda: n.m.reopen(h, p, w))
    n.ux.matches(h, p, 5)
    save('open-counts-' + str(generation) + '-' + unit + '.json',
         dict(status='PASS', unit=unit, generation=generation, dat_sha256=sha(p.dat),
              elf_sha256=sha(elf.read_bytes()), steps=steps, file_mutations=n.m.no_writes(p)))
    print('PASS open counts', generation, unit, [(x['operation'], x['RPC']) for x in steps], flush=True)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('unit', choices=('50mm', '28mm', 'mount'))
    parser.add_argument('--generation', type=int, choices=(121, 122), default=122)
    args = parser.parse_args()
    run(args.unit, args.generation)
