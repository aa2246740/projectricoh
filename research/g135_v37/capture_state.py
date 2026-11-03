"""Save final target memory and full RPC records from a retained session."""
from pathlib import Path
import hashlib
import json

ROOT = Path(__file__).resolve().parents[2]

def run(context, arguments, out, sessions):
    unit = arguments[arguments.index('--unit') + 1]
    objects = [item for session in sessions
               for item in (session if isinstance(session, tuple) else (session,))]
    products = [item for item in objects if hasattr(item, 'image_base') and hasattr(item, 'rpc')]
    assert products
    product = next(item for item in products if item.image_base)
    backend = product.h.b
    folder = out / ('target-state-' + unit)
    folder.mkdir(exist_ok=True)
    regions = []
    for index, (base, data, writable) in enumerate(backend.regions):
        name = 'region-' + str(index) + '.bin'
        (folder / name).write_bytes(bytes(data))
        regions.append(dict(base=base, bytes=len(data), writable=writable, file=name))
    (folder / 'state.json').write_text(json.dumps(dict(regions=regions,
        registers={'r' + str(i): backend.get_reg('r' + str(i)) for i in range(16)}), indent=2) + '\n')
    h01_restore(product, unit, out)
    records = [{key: value for key, value in record.items()
                if key in ('cmd', 'value', 'page', 'result', 't')} for record in product.rpc.log]
    assert records and all(set(row) == {'cmd', 'value', 'page', 'result', 't'} for row in records)
    (out / ('complete-rpc-' + unit + '.json')).write_text(json.dumps(dict(
        unit=unit, dat_sha256=hashlib.sha256(product.dat).hexdigest(), records=records)) + '\n')
    print(json.dumps(dict(name='capture-' + unit, returncode=0,
                         counts=dict(regions=len(regions), records=len(records)))))

def h01_restore(product, unit, out):
    host = product.h
    layout = json.loads((ROOT / 'research/g135_v37/adapter-layout.json').read_text())
    symbols = [value for name, value in product.elf.symbols.items()
               if name == 'n' or name.startswith('n.lto_priv.')]
    assert len(set(symbols)) == 1
    ui = product.image_base + symbols[0] + layout['ui']
    def field(name):
        return host.u(ui + layout['ui.' + name], 1)
    def call(slot, arguments=()):
        result = product.engine(slot, list(arguments))
        assert result.get('ok') and result.get('signed') == 1 and result.get('reply_status') == 0, ('H01-entry-result', slot, result)
    def settings():
        base = host.u(0x200c0dac)
        return dict(mode=host.u(base + 0x36e, 1),
                    wb=[host.u(base + 0x6dd, 1), host.u(base + 0x6de, 1)])
    initial_geometry = dict(rows=host.u(0x205d9bf8), overlay=host.u(0x2037f3bc),
                            count=host.u(0x205a27d4, 1), tag=host.u(0x205a279c, 1))
    for address, value, size in ((0x205d9bf8, 8, 4), (0x205d9c00, 56, 4),
            (0x205a280f, 2, 1), (0x2037f3bc, 32, 4), (0x205a27d8, 0x205a279c, 4),
            (0x205a27d4, 1, 1), (0x205a279c, 32, 1), (0x205a27a0, 0x2022f71c, 4)):
        host.put(address, value, size)
    call(1)
    for _ in range(16):
        current = field('cur')
        if current == 3:
            break
        direction = 1 if current < 3 else -1
        physical = (field('physical') + direction) % 8
        host.put(0x2022f726, physical + 1, 1)
        call(6, [physical])
    assert field('cur') == 3, ('H01-stock-cursor', field('cur'))
    before = settings()
    assert before == dict(mode=1, wb=[9, 9]), ('H01-stock-settings', before)
    base = host.u(0x200c0dac)
    for offset, value in ((0x36e, 3), (0x6dd, 1), (0x6de, 17)):
        host.put(base + offset, value, 1)
    reset = settings()
    assert reset == dict(mode=3, wb=[1, 17]), ('H01-simulated-reset', reset)
    call(1)
    after = settings()
    assert after == dict(mode=1, wb=[9, 9]) and host.u(0x205d9bf8) == 8, ('H01-reopened-settings', after)
    result = dict(status='PASS', unit=unit, before=before, simulated_reset=reset,
                  reopened=after, rows=8, initial_geometry=initial_geometry,
                  entry_geometry=dict(rows=8, count=1, tag=32, overlay=32),
                  dat_sha256=hashlib.sha256(product.dat).hexdigest())
    (out / ('h01-restore-' + unit + '.json')).write_text(json.dumps(result, indent=2) + '\n')
