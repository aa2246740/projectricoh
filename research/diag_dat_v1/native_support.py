"""Pinned body plus final diagnostic DAT, using official native constructors."""
from pathlib import Path
import copy
import json
import struct
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from scope import *

CANDIDATE = ENGINE / 'candidate/local/full-r13/GXRCE.DAT'
DAT = PACKAGE / 'local/SD_ROOT/GXRCE.DAT'
assert DAT.read_bytes()==CANDIDATE.read_bytes(), 'Package must contain the final compiled DAT'
ELF = ENGINE / 'candidate/local/full-r13/engine.elf'
BODY = ROOT / 'firmware/package_v36_g120b/SD_ROOT/ilaunch3'
BODY_SHA = '50720c80696ca88f25dc25a85285acd0e0f19906e1d7da1dd404f6cc243f9008'
sys.path.insert(0, str(ROOT / 'firmware/engine_v43_fix'))
m = load(ROOT / 'firmware/engine_v43_fix/integration_native.py', 'diag_native_integration')
v,fr,pe = m.v,m.fr,m.pe
m.DAT = DAT
pe.STAGED,pe.STAGED_SHA,pe.ENGINE_ELF = DAT,sha(DAT),ELF
v.python_backend.CACHE = OUT / 'local/decode' / str(os.getpid())
pe.UNITS['mount'] = (ROOT/'firmware/package_v36_g120b/SD_ROOT/l08firm3',
                    '0a4dff6d3be9b9a9b56dfcbd98a2df59efcb31f7d4eaca6b0c3fbdb1641fde44',2)
pe.FileEdge,fr.Product = m.Files,m.Product
v.harness_mod.Harness = v.V35Harness
fr.OBSERVE = v.Elf(v.RESIDENT_ELF).symbols['rv_hook_observe']
fr.LAND = {v.Elf(v.RESIDENT_ELF).symbols['rv_skip_06']:'h06_skip',
           v.Elf(v.RESIDENT_ELF).symbols['rv_close_07']:'h07_close',
           v.Elf(v.RESIDENT_ELF).symbols['rv_skip_08']:'h08_skip',
           0x202871dc:'native_setter',0x202bb96c:'native_h08',
           0x20268768:'native_setter_store',0x20268774:'native_row_store'}

LAYOUT = json.loads((OUT / 'layout.json').read_text())
N_OFFSETS = json.loads((OUT / 'local/offsets.json').read_text())
UI_RANGES = ((0x2022f5a8,0x2022f5b0),(0x2022f71c,0x2022f73c),(0x2037f3bc,0x2037f3c0),
             (0x205a279c,0x205a27e0),(0x205a280c,0x205a2814),(0x205a293c,0x205a2948),
             (0x205d9bf8,0x205d9c04),(0x205d4f64,0x205d4f68))


def need(result):
    assert result.get('ok'), result
    return result


def symbol(p, name):
    actual = next((x for x in (name,name+'.constprop.0',name+'.lto_priv.0') if x in p.elf.symbols),name)
    return p.image_base+p.elf.symbols[actual]


def private(h,p,name,width=4):
    return h.u(symbol(p,'n')+N_OFFSETS[name],width)


def text_rows(h,p):
    at=symbol(p,'n')+N_OFFSETS['rows']
    return [h.b.read(at+9*i,9).split(b'\0',1)[0].decode('ascii') for i in range(8)]


def snapshot(h,p):
    r = fr.root_fields(h)
    return dict(root=r,rows=h.u(0x2022f5ac,1),cursor=h.u(0x2022f726,1),
        marker=h.u(0x2022f725,1),cache=h.u(0x205a2944,1),overlay=h.u(0x2037f3bc),
        text=text_rows(h,p) if p.image_base else None,
        opens=private(h,p,'opens') if p.image_base else None,
        page=private(h,p,'page',1) if p.image_base else None,
        mode=h.u(h.settings+0x36e,1),activity=h.u(0x205d9bf8),native_state=h.u(0x205d9c00))


def shadow(h):
    h.b.map(0x206a0000,bytes(0x10000))
    b=v.PythonBackend()
    b.regions,b.mmio,b.traces=h.b.regions,h.b.mmio,h.b.traces
    b.breakpoints={k:list(x) for k,x in h.b.breakpoints.items()}
    b.core.r,b.core.psw=list(h.b.core.r),h.b.core.psw
    b.core.cr=dict(h.b.core.cr)
    b.core.bpsw,b.core.bbpsw,b.core.acc=h.b.core.bpsw,h.b.core.bbpsw,h.b.core.acc
    b.set_reg('r15',0x206afff0)
    other=copy.copy(h);other.b=b
    return other


def setup(unit,ready=1,link=1):
    assert sha(BODY)==BODY_SHA
    h,p,w=m.boot(unit,ready=ready,link=link)
    # The menu runs on task 6. These are RTOS observation boundaries, not UI
    # presets. Service 400 is the same normal-task context model as V10 replay.
    h.stub(0x0500c6ec,'kernel_context',value=0)
    def task_id(b):
        b.write(b.core.r[4],(6).to_bytes(2,'big'))
        return 0
    h.stub(0x0500c574,'kernel_task_id',task_id)
    # No recipe CRC function exists in this DAT. Keep all DAT instructions real.
    fr.accelerate=lambda product: product.image_base
    arm=[None]
    def entering(b):
        block=h.u(pe.ROOT_ADDR+56)
        if block:
            p.image_base=h.u(block+312)
            if arm[0]:arm[0]()
        return False
    h.b.add_breakpoint(h.symbols['rv_invoke'],entering)
    return h,p,w,arm


def open_menu(h,p):
    h.parent()
    need(fr.native(h,0x20287080,steps=30000000))
    assert p.image_base and h.u(pe.ROOT_ADDR+5,1)==3,snapshot(h,p)
    assert h.u(0x2022f5ac,1)==8,snapshot(h,p)
    return snapshot(h,p)


def action(h,p,name):
    if name in ('up','down'):
        return need(fr.move_key(h,0x1f if name=='up' else 0x20,steps=30000000))
    if name=='disp':return need(fr.native(h,0x202be220,steps=30000000))
    if name in ('ok','adj'):return need(fr.press(h,0x23 if name=='ok' else 0x2b,steps=30000000))
    if name=='half':
        h.select_item_8()
        first=need(fr.native(h,0x2029fdc4,(0x29,0),steps=30000000))
        return dict(first=first,second=need(fr.native(h,0x202bd724,(0x29,0),steps=30000000)))
    raise ValueError(name)
