"""Observe the inherited interval at the final native preview bridge."""
from pathlib import Path
import hashlib
import json

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / 'research/g131_merge'

def run(context, arguments, out, sessions):
    unit = arguments[arguments.index('--unit') + 1]
    products = [item for session in sessions for item in
        (session if isinstance(session, tuple) else (session,))
        if hasattr(item, 'image_base') and hasattr(item, 'rpc') and item.image_base]
    assert products
    product = products[0]
    host, backend = product.h, product.h.b
    def retained_observer(callback):
        code = getattr(callback, '__code__', None)
        return code is not None and Path(code.co_filename).name == 'native_checks.py'
    for address, callbacks in backend.breakpoints.items():
        backend.breakpoints[address] = [callback for callback in callbacks if not retained_observer(callback)]
    backend.traces = [(lo, hi, callback) for lo, hi, callback in backend.traces
                      if not retained_observer(callback)]
    layout = json.loads((WORK / 'adapter-layout.json').read_text())
    def symbol(name):
        values = [value for key, value in product.elf.symbols.items()
                  if key == name or key.startswith(name + '.lto_priv.')]
        assert len(set(values)) == 1
        return product.image_base + values[0]
    bridge = symbol('rv_native_preview')
    ui = symbol('n') + layout['ui']
    settings = host.u(0x200c0dac)
    observations = dict(cut_hits=0, late_native_previews=0, late_settings_stores=0)
    def cutpoint(machine):
        if observations['cut_hits']:
            return False
        host.put(0x205a27d8, 0x205a279c)
        host.put(0x205a27d4, 1, 1)
        host.put(0x205a279c, 32, 1)
        host.put(0x205a27a0, 0x2022f71c)
        host.put(0x2037f3bc, 32)
        observations['cut_hits'] += 1
        return False
    def preview(machine):
        if observations['cut_hits']:
            observations['late_native_previews'] += 1
        return False
    def store(event):
        if observations['cut_hits'] and getattr(event, 'origin', None) == 'cpu':
            observations['late_settings_stores'] += 1
    initial = product.engine(1, [])
    assert initial.get('ok') and initial.get('signed') == 1
    backend.add_breakpoint(bridge, cutpoint)
    backend.breakpoints.setdefault(0x202d6f38, []).insert(0, preview)
    backend.add_write_trace(settings, settings + 0xc9e, store)
    physical = (host.u(ui + layout['ui.physical'], 1) + 1) % 8
    host.put(0x2022f726, physical + 1, 1)
    result = product.engine(6, [physical])
    if observations['cut_hits'] != 1:
        fields = {name: host.u(ui + layout['ui.' + name], 1)
                  for name in ('screen', 'cur', 'top', 'physical', 'count', 'slot', 'param')}
        (out / ('window-state-' + unit + '.json')).write_text(json.dumps(dict(
            fields=fields, observations=observations, result=result), indent=2) + '\n')
    assert result.get('ok'), 'target entry completion'
    assert observations['cut_hits'] == 1, 'native preview interval reached'
    data = dict(status='OPEN' if observations['late_native_previews'] else 'OBSERVED_ZERO',
        unit=unit, dat_sha256=hashlib.sha256(product.dat).hexdigest(),
        elf_sha256=hashlib.sha256((ROOT / 'firmware/engine_v51_g131/candidate/local/full-r13/engine.elf').read_bytes()).hexdigest(),
        bridge_address=bridge, native_address=0x202d6f38, resident_entry=8, engine_slot=6,
        rule='strict', simulated_parent_tag=32, simulated_parent_count=1, **observations)
    (out / ('observed-preview-window-' + unit + '.json')).write_text(json.dumps(data, indent=2) + '\n')
    print(json.dumps(dict(name='observed-preview-window-' + unit, returncode=0, counts=observations)))
