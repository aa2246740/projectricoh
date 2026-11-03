"""Check current Studio user-row output against the existing independent C receipt."""
from pathlib import Path
import hashlib
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import infer as i
c=i.c
dat,entries=i.store.entries_from_dat((c.ROOT/i.DAT['g150']).read_bytes())
bank=i.candidates(entries,2,dat)
rows={}
for name,rel in [('GRN*001','GRN_001.bin'),('FCC-001','FCC-001.bin'),('FCC*002','FCC_002.bin')]:
    known=(c.ROOT/'research/mount_g150_field/users'/rel).read_bytes()
    rows[name]=dict(equal=known==bank[name],sha256=hashlib.sha256(bank[name]).hexdigest())
assert all(r['equal'] for r in rows.values())
c.dump('candidate_equality.json',rows)
c.finish('candidate-equality')
print('PASS',len(rows),'complete 552-byte entries')
