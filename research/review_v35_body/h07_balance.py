"""Observe native H07 call/return SP and callee-saved registers."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from review_common import HERE,save as original_save
exec(compile((HERE/"adversarial.py").read_text().split('selected=sys.argv')[0],str(HERE/"adversarial.py"),"exec"),globals())
def save(name,value):original_save("h07-balance-"+name,value)
h,p,w=boot();records=[];pending=[]
def enter(b):
    row=dict(entry="0x202871d8",sp=b.get_reg("r15"),lr=hex(b.get_reg("r14")),
             saved=[b.get_reg("r"+str(i)) for i in range(8,14)])
    pending.append(row);records.append(row);return False
def leave(b):
    if pending:
        row=pending.pop();row.update(return_pc=hex(b.pc),return_sp=b.get_reg("r15"),
            return_saved=[b.get_reg("r"+str(i)) for i in range(8,14)])
        row["stack_balanced"]=row["sp"]==row["return_sp"]
        row["r8_to_r13_preserved"]=row["saved"]==row["return_saved"]
    return False
h.b.add_breakpoint(0x202871d8,enter)
for address in (0x202c2d74,0x202c2d84):h.b.add_breakpoint(address,leave)
rec=dict(name="H07_register_balance",steps=[]);reports.append(rec)
for label,fn in (OPEN,ONE,OK,MENU):step(rec,label,h,p,w,lambda fn=fn:fn(h,p,w))
original_save("h07-register-balance.json",records)
assert len(records)==2 and not pending
assert all(x["stack_balanced"] and x["r8_to_r13_preserved"] for x in records)
print("PASS real H07 OK and early MENU: SP balanced and r8..r13 preserved",flush=True)
