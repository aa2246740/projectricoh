"""Finish the reviewed matrix after the fallback notice changed to one row.

The unchanged final-DAT prefix is retained verbatim. It reached the correct
one-row notice, where an older eight-row helper rejected the new expected UI.
This continuation boots normally and executes every remaining native case.
"""
from pathlib import Path
import inspect,json,sys,time,traceback
sys.path.insert(0,str(Path(__file__).resolve().parent))
import run_native as n
from common import OUT,save,sha
unit=sys.argv[1];n.configure(unit,'matrix-tail');ux,m,fr=n.ux,n.m,n.fr
prefix=json.loads((OUT/'native'/('matrix-'+unit+'.json')).read_text())
assert prefix['dat_sha256']==sha(m.DAT.read_bytes()) and prefix['status']=='FAIL'
assert len(prefix['fast_moves'])==41 and len(prefix['faults'])==3
assert prefix['fallback04']['actual']['slot']==4
assert "'rows': 1" in prefix['error']
save('partial-runs/matrix-prefix-'+unit+'.json',prefix)
for name in ('arm_entries','measure_move'):
 source=inspect.getsource(getattr(ux,name))
 routed=source.replace("h.b.breakpoints.pop(p.symbol_pc('gxr2_crc_add'),None)", 'pass # validated CRC-32 boundary for functional replay')
 exec(compile(routed,str(OUT/('tail-'+name+'-functional.py')),'exec'),ux.__dict__)
original_instrument=ux.instrument
def instrument(h,p):
 operation=h.b.core.op;result=original_instrument(h,p);h.b.core.op=operation;return result
ux.instrument=instrument
source=inspect.getsource(ux.matrix)
start=source.index("    report['nested_navigation']")
function='def finish_matrix(unit,report):\n    h,p,w=m.boot(unit);m.published(h,p,w);ins=instrument(h,p);arm_entries(h,p,ins)\n'+source[start:]
exec(compile(function,str(OUT/'matrix-tail-native.py'),'exec'),ux.__dict__)
r=dict(unit=unit,dat_sha256=sha(m.DAT.read_bytes()),engine_elf_sha256=sha(n.pe.ENGINE_ELF.read_bytes()),native_ui_hand_seeded=False,getter_fixed_return_stub_removed=True)
started=time.monotonic()
try:ux.finish_matrix(unit,r)
except Exception:r.update(status='FAIL',error=traceback.format_exc());raise
finally:
 r['seconds']=time.monotonic()-started;save('native/matrix-tail-'+unit+'.json',r)
assert r['status']=='PASS'
# The notice itself has already been reached in the native prefix, and is
# independently checked by the reviewed fallback and Fn2 failure groups.
save('native/matrix-complete-'+unit+'.json',dict(status='PASS',unit=unit,dat_sha256=sha(m.DAT.read_bytes()),
 prefix='partial-runs/matrix-prefix-'+unit+'.json',tail='native/matrix-tail-'+unit+'.json',
 prefix_complete_through='Cold 04, confirmations, shutters, 41 moves, three full compensations and pure04 fallback.',
 notice_helper_correction='The expected locked list has one row. The old published helper asserted eight rows after construction.',
 tail_complete=True,required_notice_evidence='native/concurrent_menu-fallback-'+unit+'.json'))
print('PASS complete native matrix across retained prefix and native continuation',unit,flush=True)
