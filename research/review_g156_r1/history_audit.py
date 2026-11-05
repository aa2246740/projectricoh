"""Retain historical failures and check which current evidence supersedes them."""
from pathlib import Path
import json
import struct
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import common as C
C.setup()
E=C.ORIGINAL/'evidence'
def read(name):return json.loads((E/name).read_text())
current=json.loads((C.HERE/'evidence/receipt_audit.json').read_text())
assert len(current['rows'])==9 and all(r['status']=='PASS'for r in current['rows'])
names=read('r3-final-matrix.json')['unconfirmed_native_attempts'];assert len(names)==5
rows=[]
for name in names:
    old=read(name);assert old['status']in('FAIL','OPEN')and old['backend']=='native'
    row=dict(receipt=name,status=old['status'],sha256=C.sha((E/name).read_bytes()),
             DAT_sha256=old['DAT_sha256'],error=old.get('error'),
             resolution='superseded by independently audited current reference; not claimed as same-input rerun')
    if '50mm-flow'in name:
        final=read('r4-reference-release-50mm-flow.json')
        expected={x['name']:x.get('readback',x)['sha256']for x in final['checks']}
        assert all(expected.get(x['name'])==x['sha256']for x in old['checks'])
        allowed={0x36e,0x36f,0x370,0x371,0x6dd,0x6de,*range(0x641,0x647),*range(0x8ac,0x8b6),*range(0xfd4,0xffc)}
        outside=set(old['S_changed_offsets'])-allowed;sites={x:set()for x in outside}
        for profile in ('release','test'):
            final=read('r4-reference-'+profile+'-50mm-flow.json')
            audit=final.get('settings_write_audit',final.get('write_whitelist'))
            for off,n,pc in audit['body_stores']:
                for x in set(range(off,off+n))&outside:sites[x].add(hex(pc))
        assert all(sites.values())
        row['body_offsets']={hex(x):sorted(y)for x,y in sites.items()}
    elif '28mm'in name:
        final=read('r4-reference-test-28mm-flow.json')
        assert final['ADJ_close']and final['OK_close']and len(final['checks'])==1
        row['current_receipts']=['r4-reference-test-28mm-flow.json','r4-reference-test-28mm-restore.json']
    else:
        assert old['stop']['reason']=='breakpoint'and(old['root'],old['state'],old['word'])==('03',5,2)
        row['current_receipts']=['r4-reference-release-50mm-flow.json']
    rows.append(row)
for old_name,new_name in [('r4-reference-release-28mm-flow.json','r4-reference-release-28mm-flow-r2.json'),
                          ('r4-reference-test-mount-restore.json','r4-reference-test-mount-restore-r2.json')]:
    old,new=read(old_name),read(new_name)
    assert old['status']=='FAIL'and new['status']=='PASS'and old['DAT_sha256']==new['DAT_sha256']
    if '28mm'in old_name:
        assert old['input_medium_sha256']==new['input_medium_sha256']
        assert new['ADJ_close']and new['OK_close']
    else:
        assert old['target_sha256']==new['target_sha256']
        assert old['restore_readback']['sha256']==new['restore_readback']['sha256']
    rows.append(dict(receipt=old_name,status='FAIL',error=old.get('error'),
        DAT_sha256=old['DAT_sha256'],current_receipt=new_name,current_status='PASS',
        same_DAT=True,resolution='new full reference receipt, independently audited'))
C.save(C.HERE/'evidence/history.json',dict(status='PASS',rows=rows))
print(json.dumps(dict(status='PASS',historical_rows=len(rows))))
