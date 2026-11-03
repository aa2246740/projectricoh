"""Verify the saved unit bytes without using the implementation's decoder."""
from pathlib import Path
import hashlib
import json
import struct
import time

ROOT=Path('/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh')
OUT=Path(__file__).resolve().parent
EVIDENCE=OUT/'runtime/evidence'
sha=lambda b:hashlib.sha256(b).hexdigest()
u16=lambda b,o:struct.unpack_from('>H',b,o)[0]
u32=lambda b,o:struct.unpack_from('>I',b,o)[0]


def builtin(raw,unit,slot):
    directory=u32(raw,156)+64*unit
    table=u32(raw,directory+20)
    entries=[raw[table+16+20*i:table+36+20*i] for i in range(raw[directory+30])]
    descriptor=next(e for e in entries if e[0]==slot)
    pool=u32(raw,192)
    lengths=(62,33,96,56)
    rows=[]
    for kind,index in zip((0,1,2,3,0,1,1,1,0,1),descriptor[8:18]):
        assert index<u16(raw,pool+16+12*kind)
        at=pool+u32(raw,pool+20+12*kind)+index*lengths[kind]
        rows.append(raw[at:at+lengths[kind]])
    combined=rows[:6]+[rows[6]+rows[7]]+rows[8:]
    assert len(combined)==9 and sum(map(len,combined))==503
    return combined,descriptor[2:4]


def main():
    tick=time.monotonic()
    raw=(ROOT/'firmware/package_v38_g152_test/local/SD_ROOT/GXRCE.DAT').read_bytes()
    assert sha(raw)=='88ca8b46c5f4f1590adfa613828ba1bfe808b23779111651d0a2ebb69c489e2b'
    rows={slot:builtin(raw,2,slot) for slot in (2,4,5,8)}
    serialized={slot:b''.join(r)+t for slot,(r,t) in rows.items()}
    saved={name:(EVIDENCE/f'after-refusal-4-mount-{name}.bin').read_bytes()
           for name in ('before','after','reopened')}
    assert saved['before']==serialized[4]
    assert saved['after']==saved['reopened']==serialized[2]
    assert saved['after'] not in (serialized[4],serialized[5],serialized[8])
    settings={name:(EVIDENCE/f'after-refusal-4-mount-{name}-S.bin').read_bytes()
              for name in ('before','after','reopened')}
    assert settings['before']==settings['after']==settings['reopened']
    assert len(settings['before'])==4096 and settings['before'][0x36e]==4
    observation=json.loads((EVIDENCE/'after-refusal-4-mount-observation.json').read_text())
    assert observation['before']['W']==0 and observation['after']['W']==506
    assert observation['calls']==[{'op':6,'returned':0},{'op':2,'returned':-2}]
    assert observation['S_stores']==[] and observation['frame']['failed']==0
    assert observation['reopened_frame']['failed']==0 and observation['frame']['slot']==4
    assert observation['flags_after_first_exit']==dict(baseline='00',committed='00',live_verified='01',uncertain='00',snapshot_fault='00')
    previous=[]
    for unit in ('mount','50mm'):
        unit_id=2 if unit=='mount' else 0
        record_path=EVIDENCE/f'after-refusal-8-{unit}-observation.json'
        if not record_path.exists(): record_path=EVIDENCE/f'after-refusal-observation-{unit}.json'
        record=json.loads(record_path.read_text())
        expected={slot:[sha(row) for row in builtin(raw,unit_id,slot)[0]] for slot in (2,4,5,8)}
        assert record['before']['rows']==expected[8]
        assert record['after']['rows']==record['after_reopen']['rows']==expected[2]
        assert record['after']['rows'] not in (expected[4],expected[5],expected[8])
        assert record['before']['S_sha256']==record['after']['S_sha256']==record['after_reopen']['S_sha256']
        previous.append(dict(unit=unit,actual_prior=8,observed=2,target=5,unit_W=record['after']['W']))
    result=dict(status='CONFIRMED_P1',dat_sha256=sha(raw),unit='mount',actual_prior=4,observed=2,target=5,
                saved_bytes={name:dict(bytes=len(value),sha256=sha(value)) for name,value in saved.items()},
                all_4096_S_bytes_retained=True,S_sha256=sha(settings['before']),unit_W=506,
                prior_two_unit_witnesses=previous,seconds=time.monotonic()-tick,
                scope='Independent final DAT reader and saved unit bytes. Explicit row-state model inputs; no camera observation.')
    (OUT/'witness_check.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result),flush=True)


if __name__=='__main__':main()
