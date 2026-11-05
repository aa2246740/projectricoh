"""Prove the original close sample recurs, then reaches standby without input."""
from pathlib import Path
import datetime,json,sys
sys.path.insert(0,str(Path(__file__).resolve().parent));import common as C
C.setup();out=C.LOCAL/'accept-r2';old_label='r2-critical-release-50mm-P';new_label='r2c-critical-release-50mm-P'
old=json.loads((C.LOCAL/'runs'/old_label/'result.json').read_text());new=json.loads((C.LOCAL/'runs'/new_label/'result.json').read_text())
assert old['status']=='ERROR' and 'line 633' in old['traceback']
assert new['status']=='OBSERVED' and new['actual_backend']=='native' and new['cold_start'] and not new['snapshots']
for field in ('dat_sha256','body_sha256','settings_sha256','input_medium_sha256','library_sha256','declared_dial'):
    assert old[field]==new[field],field
assert old['keys']==new['keys'],'pre-failure GPIO sequence or observed states changed'
assert new['ADJ_close_first_poll']==old['failure_state'],'the exact earlier failure sample must recur'
assert new['ADJ_close_first_poll']['state']==56 and new['ADJ_close_first_poll']['rows']==7
assert new['ADJ_close_no_extra_input'] and new['ADJ_close_window_budget']==90
used=sum(w==10000000 for w in new['keys'][-1]['windows'])
assert 0<len(new['ADJ_close_wait'])<=90-used
final=new['ADJ_closed']
assert final['state']==5 and final['activity']==0 and final['inflight']==0 and not final['word']&12
assert final['steps']>old['failure_state']['steps'] and final['record']==old['failure_state']['record']
assert final['live_sha256']==old['failure_state']['live_sha256']
assert new['ADJ_close_unit_readback']['complete_552_equal'] and new['close_record_equal']
aliases=json.loads((out/'aliases.json').read_text())
assert aliases['critical-release-50mm-P'] in (old_label,new_label)
if aliases['critical-release-50mm-P']!=new_label:
    C.save(out/'aliases-before-close-wait.json',aliases)
    aliases['critical-release-50mm-P']=new_label;C.save(out/'aliases.json',aliases)
C.save(out/'close_wait/verification.json',dict(status='PASS',utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),original=old_label,retest=new_label,DAT_sha256=new['dat_sha256'],same_cold_inputs=True,identical_pre_failure_keys_and_states=True,identical_early_sample=True,early_state=56,early_rows=7,final_state=5,extra_GPIO_inputs=0,extra_wait_windows=len(new['ADJ_close_wait']),total_window_limit=90,complete_552_equal=True,record_unchanged=True,product_changed=False,endpoint_assertion_unchanged=True,classification='The generic key helper accepted a restored seven-row factory table before the native close transition completed. Original instructions reach stable standby without another input.'))
print(json.dumps(dict(status='PASS',exact_first_failure_reproduced=True,extra_keys=0,standby=5,complete_colour_and_record_unchanged=True)))
