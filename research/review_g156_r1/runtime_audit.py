"""Audit newly executed samples without trusting their PASS strings alone."""
from pathlib import Path
import json
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import common as C
C.setup()
helpers=C.HERE/'receipt_audit.py'
scope={'__file__':str(helpers)}
exec(compile(helpers.read_text().split('records=json.loads')[0],str(helpers),'exec'),scope)
writes=scope['writes']
records=json.loads((C.HERE/'evidence/records.json').read_text())['rows']
out=[]
labels=['review-release-50mm-native','review-release-bw-close-native',
        'review-old-g155c-native','review-old-g155c-reference']
for label in labels:
    path=C.HERE/'evidence'/(label+'.json');d=json.loads(path.read_text())
    assert d['status']=='PASS'and d['body_sha256']=='a04f1ed40143b2c54d7f28e3af8af1f9a5ef5e115edf49eb404b8e26a53509c8'
    assert d['policy']=='strict'and d['backend']==d['actual_backend']
    raw=(C.PACKAGES[d['profile']]/'GXRCE.DAT').read_bytes()
    assert d['DAT_sha256']==C.sha(raw)
    source=C.ROOT/d['driver_source_copy'];assert C.sha(source.read_bytes())==d['driver_sha256']
    assert 'storage_run.Machine(str(medium))'in source.read_text()
    assert 'load_snapshot'not in source.read_text()and'restore_snapshot'not in source.read_text()
    log_path=C.ROOT/d['rpc_log_path'];assert C.sha(log_path.read_bytes())==d['rpc_log_sha256']
    log=json.loads(log_path.read_text());audit=writes(raw,0,log)
    first=d['first_menu'];assert first['cursor']==first['cached']==first['physical']+1
    assert(first['state'],first['activity'],first['word'])==(56,8,2)
    row=dict(label=label,status='PASS',backend=d['actual_backend'],profile=d['profile'],
        receipt=str(path.relative_to(C.ROOT)),receipt_sha256=C.sha(path.read_bytes()),
        DAT_sha256=C.sha(raw),driver_sha256=d['driver_sha256'],
        raw_rpc_log_sha256=d['rpc_log_sha256'],unit_write_audit=audit,final_steps=d['final_steps'])
    if 'old-g155c'in label:
        assert d['old_record_clean_reject']and d['record_40B_preserved']and audit['unit_W']==0
        assert d['old_record_552_stock']['sha256']==C.sha(C.DF.expand(raw,0,4))
        assert d['old_record_552_stock']['complete_552_equal']
        assert first['levels']==[100,0,0,0,0,0,0,0,0,0]
        if label.endswith('reference'):
            assert d['settings_sha256']==json.loads((C.HERE/'evidence/old-record-fixture.json').read_text())['fixture_sha256']
        row.update(old_record_clean_reject=True,full_552_stock=True,record40_preserved=True,
                   settings_stores='not emitted by early-return sample; nine reference receipts separately audit S')
    else:
        expected={r['name']:r['sha256']for r in records if r['profile']=='release'and r['unit']=='a12-50'and r['action']=='replace'}
        if 'bw-close'in label:expected={n:expected[n]for n in ('03 HC BW','Tri-X 400')}
        checks={x['name']:x['sha256']for x in d['checks']}
        assert checks==expected and len(d['checks'])==len(expected)
        for check in d['checks']:
            assert check['complete_552_equal']and check['cursor_equal']and check['cursor_after_DISP']and check['DISP_no_write']
            if 'bw-close'in label:
                assert check['OK_close_this_recipe']and check['ADJ_close_this_recipe']
        assert d['OK_close']and d['ADJ_close']
        assert any(k['key']=='OK'and k['state']['state']==5 and k['state']['word']==2 for k in d['keys'])
        assert any(k['key']=='ADJ'and k['state']['state']==5 and k['state']['word']==2 for k in d['keys'])
        assert writes(raw,0,log,0,d['unit_log_start'])['unit_W']==0
        row.update(records=checks,OK_close=True,ADJ_close=True,release_BOOT_unit_W=0,
                   each_recipe_both_closes='bw-close'in label)
    out.append(row)
C.save(C.HERE/'evidence/runtime_samples.json',dict(status='PASS',rows=out,
    boundary='New Machine cold starts only. Native S writes are not substituted for the independent existing reference S audits.'))
print(json.dumps(dict(status='PASS',samples=len(out))))
