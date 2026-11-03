"""Check complete case counts and literal expected acceptance values."""
from pathlib import Path
import json
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import OUT, DAT_SHA, save

def read(name):return json.loads((OUT/name).read_text())

units=[]
for unit in ('50mm','28mm','mount'):
    matrix=read('native/matrix-'+unit+'.json')
    assert matrix['status']=='PASS' and matrix['dat_sha256']==DAT_SHA
    assert len(matrix['fast_moves'])==41
    fn=read('native/fn2-four-parameters-'+unit+'.json')
    assert fn['status']=='PASS' and fn['dat_sha256']==DAT_SHA and len(fn['parameters'])==4
    expected=('contrast','saturation','highlight','shadow')
    total=0
    for index,row in enumerate(fn['parameters']):
        assert row['parameter']==expected[index]
        points=row['points']
        assert [p['point'] for p in points]==list(range(1,row['reference']['RPC']+1))+['preview']
        assert all(p['late_writes']==0 and p['complete'] in (['old'],['new']) for p in points)
        total+=len(points)
    assert total==182
    h07=read('native/h07-all-'+unit+'.json')
    assert h07['status']=='PASS' and h07['dat_sha256']==DAT_SHA
    assert len(h07['cases'])==(32 if unit=='28mm' else 28)
    assert all(row['RPC']==row['W']==row['preview']==0 for row in h07['cases'])
    latch=read('native/latch-paths-'+unit+'.json')
    assert latch['status']=='PASS' and latch['dat_sha256']==DAT_SHA
    assert [row['failure_at'] for row in latch['states']]==[1,16]
    for row in latch['states']:
        assert row['RPC']==row['W']==row['preview']==0 and len(row['cases'])==10
        assert row['notice']['text'] and all(text=='ERR POWER OFF/ON' for text in row['notice']['text'])
        assert row['notice']['draws']
    measure=read('native/fn2-step-counts-'+unit+'.json')
    assert measure['status']=='PASS' and measure['dat']==DAT_SHA and len(measure['steps'])==80
    assert {text[:4] for text in measure['native_ascii_labels']}=={'Cont','Satu','HiLt','Shad'}
    names=read('native/names-'+unit+'.json')
    assert names['status']=='PASS' and names['dat']==DAT_SHA and names['all_eight_drawn']
    assert len(names['names'])==8
    current=read('h07-sync-native-'+unit+'.json')['reentry_cases'][0]
    baseline=read('h07-sync-gen117-native-'+unit+'.json')['reentry_cases'][0]
    assert current['call']['ok'] and baseline['call']['ok']
    assert current['owned']==baseline['owned']==0
    assert len(current['native_ui_writes'])==5 and len(baseline['native_ui_writes'])==4
    assert {row['address'] for row in current['native_ui_writes']}-{row['address'] for row in baseline['native_ui_writes']}=={'0x205a2944'}
    units.append(dict(unit=unit,matrix_steps=41,fn2_switch_points=total,h07_cases=len(h07['cases']),
                      latch_api_calls=20,fn2_steps=80,names=8,h07_condition_c=False))
save('feature-check.json',dict(status='PASS',dat_sha256=DAT_SHA,units=units,
                              switch_points=546,h07_cases=88,latch_api_calls=60,fn2_steps=240,names=24))
print('PASS feature counts and expected values: 546 switch points, 88 H07 cases, 60 latch API calls, 240 Fn2 steps, 24 names',flush=True)
