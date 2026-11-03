"""Verify the first-publication counterexample and its two-generation controls."""
from pathlib import Path
import hashlib
import json
OUT=Path(__file__).resolve().parent;ROOT=OUT.parents[1]
PIN='ebf07faa3c5b8dcec411da7f7217fb58488adafb942045999bd2cdf7ce98f803'
records=[]
for generation,folder,cut,action in (
    (124,'cold-reentry-final','control','right'),
    (124,'cold-reentry-final','before_publish','right'),
    (124,'cold-reentry-final','before_publish','left'),
    (124,'cold-reentry-final','after_publish_restore','right'),
    (121,'cold-reentry','control','right'),
    (121,'cold-reentry','before_publish','right'),
    (121,'cold-reentry','before_publish','left'),
    (121,'cold-reentry-post8','after_publish_restore','right')):
    path=OUT/'local'/folder/(f'{generation}-50mm-{cut}-{action}.json')
    r=json.loads(path.read_text());assert r['status']!='HARNESS_ERROR'
    assert not r['native_UI']['host_ui_writes'] and not r['native_UI']['getter_callback_present']
    assert not any(r['file_mutations'].values())
    if generation==124:assert r['dat_sha256']==PIN
    if cut=='before_publish':
        n=r['nested'];assert n['before']['rows']==7 and n['before']['root']['inflight']==1
        assert n['psw']&0x40 and n['Image_mode_stores']
        assert '0x20268774' in n['setters'] or '0x20268768' in n['setters']
        assert any(x['hook']==8 and x['gate']==3 for x in n['resident_hooks'])
        if action=='right':assert r['final']['mode']==5 and not r['final_matches04']
        else:assert r['final']['mode']==1 and r['final_matches04']
        if generation==124 and action=='right':
            assert r['after_confirm_exit']['mode']==5 and r['confirm_RPC']==0
            assert r['after_exit_stock04']['matches'] is False
    elif cut=='after_publish_restore':
        assert r['nested']['before']['rows']==8 and not r['nested']['Image_mode_stores']
        assert r['final_matches04']
    else:assert r['final_matches04']
    records.append(dict(generation=generation,cut=cut,action=action,mode=r['final']['mode'],
        rows=r['final']['rows'],native_mode_stores=len(r.get('nested',{}).get('Image_mode_stores',[])),
        final_matches04=r['final_matches04'],file=str(path.relative_to(ROOT)),sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
value=dict(status='P1_REPRODUCED',dat_sha256=PIN,records=records,
    reason='Cold first-publication arrows reach the native Image setter before rows become eight. A right arrow leaves mode 5 under a published 04 list, and confirming does not repair it. Both generations reproduce the pre-publication store.')
(OUT/'evidence/cold-publication-verified.json').write_text(json.dumps(value,indent=2)+'\n')
print('P1 REPRODUCED with exact DAT, native-only UI, same-value stores and gen121 controls')
