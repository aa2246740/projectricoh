#!/usr/bin/python3
"""Independently collect final repair results from completed evidence."""
import hashlib
import json
import os
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
E=HERE/'evidence'


def read(name):return json.loads((E/(name+'.json')).read_text())


def write(name,data):(E/(name+'.json')).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')


def main():
    assert os.getpriority(os.PRIO_PROCESS,0)>=10
    positive=[]
    for recipe in ('mount-builtin','mount-look','mount-user','28mm-builtin','50mm-user'):
        name='valid-'+recipe+'-r5';a=read(name+'-acceptance');d=read(name+'-detail');m=read(name)
        assert a['status']=='PASS' and a['target_bytes']==552 and a['native_state_presets']==[]
        assert a['cache_sha256']==a['target_sha256'] and a['S_plan_equal'] and a['adjacent_rpc_bytes_unchanged']
        assert len(a['nine_rows'])==9 and all(x['equal'] for x in a['nine_rows'])
        assert [x['state'] for x in m['state_sequence']][:4]==[0,2,32,5]
        boot=[x for x in d['calls'] if x['op']==257];assert len(boot)==1
        positive.append(dict(name=name,status='PASS',first5=m['first_state5'],
            completion=a['completion_word_event'],boot_return=a['boot_return'],
            steps_from_first5=a['steps_from_first5'],target_sha256=a['target_sha256'],W=a['W'],T=a['T'],S=a['S']))
    negative=[]
    for name in ('gate-bad-crc','gate-cross-unit'):
        a=read(name+'-acceptance');assert a['status']=='PASS' and a['qualification_passed']
        assert a['W']==a['T']==a['S']==0
        negative.append(a)
    release=[]
    for unit in ('mount','28mm','50mm'):
        name='release-'+unit+'-g155b';d=read(name+'-detail');m=read(name)
        baseline=json.loads((HERE.parent/'evidence'/('nodat-'+unit+'-r1-detail.json')).read_text())
        boot=[x for x in d['calls'] if x['op']==257];assert len(boot)==1
        call=boot[0];reply=bytes.fromhex(call['reply'])
        assert call['result']==0 and int.from_bytes(reply[4:8],'big',signed=True)==-4
        assert d['counts']['H50']==1 and d['final']['word']==2 and d['final']['root_state']==3
        words=[x['word'] for x in d['fixed_word_changes']];assert words[words.index(0):]==[0,1,2]
        assert not d['all_boot_settings_writes'] and not d['dirty_settings_writes'] and not d['final']['rpc_state']
        assert d['final']['s_sha256']==baseline['final']['s_sha256']
        assert [x['state'] for x in m['state_sequence']]==[0,2,32,5]
        release.append(dict(unit=unit,status='PASS',dat_sha256=d['dat_sha256'],first5=m['first_state5'],
            boot_call=call,word=2,W=0,T=0,S=0,S_equal_nodat=True,
            model='Original byte-column NAND model; unchanged release path; unit-link responses declared'))
    identity=[]
    for unit in ('mount','28mm','50mm'):
        rows=read('identity-'+unit+'-g155b-c')['cases'];assert len(rows)==7
        assert all(x['status']=='PASS' for x in rows);identity.extend(rows)
    py=read('identity-28mm-g155b-python')['cases'];assert len(py)==7 and all(x['status']=='PASS' for x in py)
    write('repair-final-tests',dict(positive=positive,independent_negative=negative,release=release,
        identity=dict(c_passed=len(identity),python_passed=len(py)),
        first_menu='OPEN; native NAND geometry boundary before H01',
        H52=read('h52-real-mount-h52-acceptance'),
        scope='C MAIN cold runs with declared devices; host identity and pure branch replays are separate layers'))
    recovery=[]
    for name in ('restore-v310-word','restore-v39-word'):
        a=read('recovery-'+name+'-projection-1994291028')
        assert a['normal_update_exit'] and not a['header_valid'] and not a['byte_equal']
        raw=(ROOT/a['reassembled']).read_bytes();official=(ROOT/'artifacts/firmware/gxr-1.51/ilaunch3').read_bytes()
        assert len(raw)==len(official)==3993340
        assert hashlib.sha256(raw).hexdigest()==a['reassembled_sha256']
        assert sum(x!=y for x,y in zip(raw,official))==a['differing_bytes']==3911965
        recovery.append(a)
    assert recovery[0]['reassembled_sha256']==recovery[1]['reassembled_sha256']
    trace=read('recovery-restore-v39-read-trace-checksum')[-1]
    assert trace['read_return_signed']==-1 and trace['consumed']==3276800 and trace['prefix_sum_equal']
    c,p=read('recovery-read-branch-c'),read('recovery-read-branch-python')
    assert c['input_sha256']==p['input_sha256'] and c['signed_r0']==p['signed_r0']==-1 and c['steps']==p['steps']==3
    write('recovery-final-comparison',dict(status='FAIL',gate_closed=False,
        native_selected_update_completed=True,complete_official_body_recovered=False,
        native_selection='BACKUP ilaunch0 only; MAIN and EXTEND were excluded by prechecks',
        runs=recovery,read_failure=trace,python_review=dict(c=c,python=p),
        initial_nand=[x['initial_nand'] for x in read('recovery-media-audit')],
        boundary='File read fails before checksum comparison; the missing lower device or file-service behavior remains OPEN',
        next_step='Trace the actual lower file read and SD reinitialization, then repeat both complete restores and NAND readback',
        native_state_presets=[]))
    print(json.dumps(dict(positive=5,negative=2,release=3,identity_c=21,identity_python=7,
        H52='FAIL',recovery_gate_closed=False)))


if __name__=='__main__':main()
