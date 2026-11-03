"""Document the adjudicated final-check-to-draw scheduling window."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from ui_test_support import *
from safety_cases import shadow

def main():
    s=Session('50mm','remaining-window')
    s.press('DOWN');s.press('DISP')
    switched=[False];painted=[];record=dict(unit=s.unit)
    def switch(b):
        if switched[0]:return False
        assert b.core.psw&0x40
        before=s.state();other=shadow(s.h,s.v);switched[0]=True
        other.run_slice(0x202ba380,0x202ba3c8);other.leave_other_list()
        record['switch']=dict(pc=hex(b.pc),psw=b.core.psw,before=before,
                              activity_after=s.h.u(0x205d9bf8),state_after=s.h.u(0x205d9c00))
        return False
    def paint(b):
        if switched[0]:painted.append(dict(pc=hex(b.pc),state=hex(b.core.r[13]),activity=s.h.u(0x205d9bf8)))
        return False
    s.h.b.add_breakpoint(s.p.symbol_pc('rv_native_draw'),switch)
    s.h.b.add_breakpoint(0x201ffb2c,paint)
    s.h.b.core.psw|=0x40
    record['outer']=s.ux.need(s.fr.move_key(s.h,0x20,steps=30000000))
    assert switched[0] and painted,'The deliberately injected remaining window must be observed'
    record.update(status='KNOWN_WINDOW_AFTER_FINAL_OWNERSHIP_CHECK',dat_sha256=sha(s.p.dat),
                  painted_rows_after_switch=painted,rpc_log=s.p.rpc.log,native_UI=ui_audit(s.h),
                  scope='A native task is forced at the draw bridge after the final ownership check. Graphics leaves are modeled; no physical pixels or scheduling frequency is claimed.')
    save('local/remaining-window.json',record)
    save('evidence/remaining-window.json',{k:v for k,v in record.items() if k not in ('rpc_log','painted_rows_after_switch') }|
         dict(painted_row_visits=len(painted)))
    print('KNOWN_WINDOW after the last check, before native draw:',len(painted),'native row visits')

if __name__=='__main__':main()
