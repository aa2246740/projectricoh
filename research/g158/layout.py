"""Target compiler offsets; g is a pointer to the attached Engine arena."""
from pathlib import Path
import struct
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import common as C
C.setup();C.compute_gate('layout')
E=C.load(C.ROOT/'firmware/stage2l_switch/tools/build.py','g158_layout_elf').Elf
groups=[('adapter.c','Integrated','n',['ui.text','ui.levels','ui.saved','ui.screen','ui.cur','ui.top','ui.physical','ui.count','ui.slot','ui.param','ui.applied_user','ui.effect','ui.confirmed_user','values','entry','watch_view','view_lost','comm_failed']),
 ('src/firmware/engine/core/eng_core.c','Engine','g',['data.image','data.map','data.bank','data.pool','data.meta','data.ids','data.unit','data.view','port','live','current','tweak','memory_dirty','current_user','memory_blocked','settings_pending','stage','staging','memory_want','s_unwritten','uncertain','write_started','restore_done','baseline','boot_committed','saved.ref','saved.levels','saved.user','memory_result','memory_error','auto_result','stock','epoch','confirmed','confirmed_tweak','list','ready','bound','busy','committed','live_verified','snapshot_fault','s_busy','s_refused','neighbor_valid','t_checked','t_pending','confirmed_valid','previewing','memory_user','boot_active']),
 ('diagnostic.c','BootDiagnostic','diag',['failed','activity','state','selection','settings','length','mode','submode','my','pending','seen','entry','reason','stage','shown','record']),
 ('../../engine_services/services.c','RvSession','session',['context','settings','settings_bytes','settings_epoch','settings_token','capabilities','leases','image_address','code_begin','code_end','view_lease','view_source','rows']),
 ('../../engine_services/services.c','RvRoot','root',['block','inverse','lease','heap_begin','heap_end','block_bytes','alloc_bytes','code_address','code_bytes','unit','ui_block','entry_serial','lease_inverse','flags','epoch','reserved_lane'])]
offsets={};sizes={}
out=C.LOCAL/'layout';out.mkdir(exist_ok=True)
for i,(source,kind,prefix,names) in enumerate(groups):
    p=out/(str(i)+'.c');obj=p.with_suffix('.o')
    p.write_text('#include <stddef.h>\n#include "'+str((C.PRODUCT/source).resolve())+'"\nconst unsigned layout[] __attribute__((section(".g158_layout")))={sizeof('+kind+'),'+','.join('offsetof('+kind+','+n+')' for n in names)+'};\n')
    C.run([C.GCC,'-Os','-std=c11','-ffreestanding','-fno-builtin','-m32r','-msdata=none','-DG158_BOOT=1','-DPN_CORE_HEADER="../core/eng_core.h"','-DPN_GXTS_SHARED_PARAMETER','-I',C.PRODUCT,'-c',p,'-o',obj],'layout-'+str(i))
    elf=E(obj);section=next(s for s in elf.sections if s['name']=='.g158_layout')
    values=struct.unpack('>'+str(len(names)+1)+'I',elf.content(section));sizes[kind]=values[0]
    offsets.update({prefix+'.'+n:v for n,v in zip(names,values[1:])})
assert sizes['Engine']<=5120 and sizes['BootDiagnostic']<=1024
C.save(C.LOCAL/'layout.json',dict(offsets=offsets,sizes=sizes,g_is_pointer=True,arena=dict(engine=[0,5120],diagnostic=[5120,6144],ui=[6144,6400])))
print(sizes)
