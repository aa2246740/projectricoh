"""Check the fixed H07 return continuation and the real native sync state."""
from pathlib import Path
import copy
import re
import subprocess
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import native_cases as nc
from common import ROOT, OUT, DAT, DAT_SHA, save, sha, file_sha
from ui_trace_scope import touches_ui

n, ux, m, fr, v = nc.n, nc.ux, nc.m, nc.fr, nc.v

def elf_bytes(elf, address, length):
    for section in elf.sections:
        if section['base'] <= address and address+length <= section['base']+section['size'] and section['data']:
            offset = address-section['base']
            return section['data'][offset:offset+length]
    raise ValueError(hex(address))

def static():
    resident = v.Elf(v.RESIDENT_ELF)
    body = v.Image(ROOT/'firmware/package_v36_g120b/SD_ROOT/ilaunch3', v.BODY_SHA)
    baseline = v.Image(ROOT/'firmware/package_v36_g117/SD_ROOT/ilaunch3', v.BODY_SHA)
    start = resident.symbols['rv_close_07']
    data = elf_bytes(resident, start, 44)
    assert start == 0x20052be8 and data == body.bytes_at(start, 44) == baseline.bytes_at(start, 44)
    command = [str(ROOT/'research/tooling_m32r/prefix/bin/m32r-elf-objdump'), '-d',
               '--start-address='+hex(start), '--stop-address='+hex(start+44), str(v.RESIDENT_ELF)]
    result = subprocess.run(command, capture_output=True, text=True, check=True)
    listing = '\n'.join(line for line in result.stdout.splitlines()
                        if re.match(r'^\s*[0-9a-f]+(?:\s+<|:)', line))+'\n'
    (OUT/'h07-close.txt').write_text(listing)
    assert '20052bfc:' in listing and 'jl r0' in listing
    assert '20052c08:' in listing and 'st r0,@r1' in listing
    save('h07-static.json', dict(status='P1', dat_sha256=file_sha(DAT),
        resident_elf_sha256=sha(resident.raw), body_sha256=body.sha256,
        close_bytes_hex=data.hex(), close_sha256=sha(data), gen117_close_equal=True,
        call_pc='0x20052bfc', native_target='0x201c092c', return_pc='0x20052c00',
        store_pc='0x20052c0a', store_packet_pc='0x20052c08', store_address='0x2037f3bc', store_value=0,
        condition_a=False, condition_b=False,
        reason='The native layer call returns to resident instructions which clear the overlay after native UI synchronization.'))

def run(unit,native_h01=False,baseline=False):
    n.configure(unit, 'h07-boundary-review')
    if baseline:
        ux.configure(True,unit+'-gen117-sync')
    actual_dat=sha(m.DAT.read_bytes())
    prefix='gen117-' if baseline else ''
    v.python_backend.CACHE = OUT/'decode/h07-boundary'
    h, p, w = m.boot(unit)
    h.run_slice(0x2030e8cc, 0x2030e8e4)
    h.parent()
    m.published(h, p, w)
    ux.need(fr.native(h, 0x20265818, (0,)))
    chain = []
    boundary = {}
    transfer_model=list(h.b.breakpoints.get(0x201d83b0,[]))
    sync_model=list(h.b.breakpoints.get(0x2005ff88,[]))
    for address, name in ((0x20052be8, 'resident_close'), (0x201c092c, 'native_layer'),
                          (0x201d83b0, 'layer_transfer'), (0x201d79f4, 'layer_show')):
        def record(b, name=name):
            chain.append(dict(name=name, pc=hex(b.pc)))
            return False
        h.b.breakpoints.setdefault(address, []).insert(0, record)
    h.b.breakpoints[0x201d83b0] = [h.b.breakpoints[0x201d83b0][0]]
    def sync(b):
        boundary.update(pc=hex(b.pc), registers=list(b.core.r), psw=b.core.psw,
            control=dict(b.core.cr), bpsw=b.core.bpsw, bbpsw=b.core.bbpsw, acc=b.core.acc,
            state=ux.snap(h, p), stack_hex=b.read(b.core.r[15], 64).hex(),
            restore_words=[h.u(n.pe.ROOT_ADDR+156+4*i) for i in range(14)])
        return None
    h.b.breakpoints[0x2005ff88] = [sync]
    rpc = len(p.rpc.log)
    before = ux.snap(h, p)
    result = fr.press(h, 0x23)
    save('h07-boundary-progress-'+prefix+('native-' if native_h01 else '')+unit+'.json', dict(before=before, result=result,
        boundary=boundary, chain=chain, dat_sha256=actual_dat))
    assert boundary and result['reason'] == 'breakpoint' and result['pc'] == '0x2005ff88', (result, chain)
    if not baseline:
        assert len(p.rpc.log) == rpc
    context = nc.stamp(h, p)
    cases = []
    for hook in ((1,) if native_h01 else (1, 2, 5, 6, 7, 8)):
        def check(record, hook=hook):
            b = v.PythonBackend()
            b.regions, b.mmio, b.traces = h.b.regions, h.b.mmio, h.b.traces
            b.breakpoints = {pc:list(items) for pc,items in h.b.breakpoints.items()}
            b.core.r = list(boundary['registers'])
            b.core.psw = boundary['psw']
            b.core.cr = dict(boundary['control'])
            b.core.bpsw, b.core.bbpsw, b.core.acc = boundary['bpsw'], boundary['bbpsw'], boundary['acc']
            b.map(0x206a0000, bytes(0x10000))
            b.set_reg('r15', 0x206afff0)
            shadow = copy.copy(h)
            shadow.b = b
            product = copy.copy(p)
            product.h = shadow
            frame = 0x206a1000
            b.write(frame, bytes(128))
            owned = product.call(h.symbols['owned'], (n.pe.ROOT_ADDR, hook))
            assert owned['ok'] and owned['r0'] == 0
            rpc_at, preview = len(p.rpc.log), h.stub_hits.get('preview', 0)
            writes, entries = [], []
            def watch(event):
                if touches_ui(event) and event.pc is not None:
                    if 0x20052000 <= event.pc < 0x20054700 or p.image_base <= event.pc < p.image_base+len(p.dat):
                        writes.append(dict(address=hex(event.address), pc=hex(event.pc), data_hex=event.data.hex()))
            b.add_write_trace(0, 2**32, watch)
            for name in ('ig_menu', 'ig_event', 'ig_apply', 'ig_panel_open'):
                def entered(backend, name=name):
                    entries.append(name)
                    return False
                b.add_breakpoint(p.symbol_pc(name), entered)
            if native_h01:
                b.breakpoints[0x201d83b0]=transfer_model
                b.breakpoints[0x2005ff88]=sync_model
                called=fr.open_settings(shadow)
            else:
                called=product.call(h.symbols['rv_hook_observe'], (n.pe.ROOT_ADDR, hook, frame))
            assert called['ok']
            record.update(hook=hook, owned=owned['r0'], call=called,
                RPC=len(p.rpc.log)-rpc_at, W=sum(x['cmd']==22 for x in p.rpc.log[rpc_at:]),
                preview=h.stub_hits.get('preview', 0)-preview, native_ui_writes=writes,
                engine_entries=entries, continuation=hex(shadow.u(frame+4)),
                condition_c=(len(p.rpc.log)==rpc_at and h.stub_hits.get('preview',0)==preview and not writes),
                after=ux.snap(shadow, product), file_mutations=m.no_writes(p))
        row = nc.case(prefix+('sync-native-h01-' if native_h01 else 'sync-hook-final-')+unit+'-'+str(hook), check, context)
        cases.append(row)
    save('h07-sync-'+prefix+('native-' if native_h01 else '')+unit+'.json', dict(status='OBSERVED', unit=unit, dat_sha256=actual_dat,
        before=before, boundary=boundary, chain=chain, result=result, RPC_delta=len(p.rpc.log)-rpc,
        reentry_cases=cases, condition_c=all(row['condition_c'] for row in cases),
        native_h01_constructor=native_h01,
        scope='Native constructors and H07 reach the exact sync entry. A separate task stack runs either the resident hook boundary or the full official H01 constructor. Nested rendering uses the same display boundaries as the main matrix. The real scheduler and outer post-sync display are not executed.'))
    print('OBSERVED H07 sync', unit, 'condition_c', all(row['condition_c'] for row in cases), flush=True)

if __name__ == '__main__':
    static()
    for unit in ('50mm', '28mm', 'mount'):
        run(unit,'--native-h01' in sys.argv,'--gen117' in sys.argv)
