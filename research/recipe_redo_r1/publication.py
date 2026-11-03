"""Publish complete files and preserve the records consumed by a parallel build."""
import hashlib
import json
import os
from pathlib import Path

HERE=Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def atomic_bytes(path,content):
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists() and path.read_bytes()==content:
        return False
    temporary=path.with_name(path.name+'.writing-'+str(os.getpid()))
    try:
        temporary.write_bytes(content)
        os.replace(temporary,path)
    finally:
        if temporary.exists():temporary.unlink()
    return True


def save_record(path,content):
    path=Path(path)
    if path.exists() and path.read_bytes()!=content:
        path=path.with_name(path.stem+'_'+hashlib.sha256(content).hexdigest()+path.suffix)
    atomic_bytes(path,content)
    assert path.read_bytes()==content
    return path


def save_metadata_path(record_path,payload):
    path=Path(record_path).with_suffix('.json')
    if path.exists() and json.loads(path.read_text())!=payload:
        state=json.loads((HERE/'local/round2_state.json').read_text())
        path=HERE/'local/round2_record_metadata'/payload['unit']/(str(payload['index']).zfill(2)+'_'+
            hashlib.sha256(json.dumps(payload,sort_keys=True,ensure_ascii=False).encode()).hexdigest()[:20]+'.json')
    return path


def adoption(row):
    path=HERE/'local/mount_reexamination/decisions.json'
    if not path.exists():return
    decisions=json.loads(path.read_text())
    decision=next((r for r in decisions['profiles'] if (r['unit'],r['index'])==(row['unit'],row['index'])),None)
    if not decision:return
    assert decision['target_sha256']==row['target_sha256']
    assert decision['release_record_sha256']==row['current_record_sha256']
    if decision['action']=='keep_current':
        assert sha(HERE/decision['release_record_file'])==decision['release_record_sha256']
        row.update(recommendation='keep_current_after_exact_review',
            deployment_action='keep_current',deployment_record_file=decision['release_record_file'],
            deployment_record_sha256=decision['release_record_sha256'],
            build_block_reason=decision['reason'],mount_reexamination=decision,
            research_candidate_is_not_the_deployment_record=True)


def stability(registry):
    path=HERE/'local/round2_state.json'
    if not path.exists():return
    state=json.loads(path.read_text())
    baseline=state['baseline_record_shas']
    allowed={f'a12-28/{i:02d}' for i in range(35)}|{'mount-a12/00','mount-a12/01'}
    if state.get('probe2_response_incorporated_sha256'):
        allowed|={f'mount-a12/{i:02d}' for i in range(35)}
    changes=[]
    for row in registry['profiles']:
        key=f'{row["unit"]}/{row["index"]:02d}'
        old=baseline[key]
        if old['record_sha256']!=row['record_sha256']:
            assert key in allowed, ('Unrequested record change',key)
            changes.append(dict(unit=row['unit'],index=row['index'],name=row['name'],
                before_record_file=old['record_file'],before_sha256=old['record_sha256'],
                after_record_file=row['record_file'],after_sha256=row['record_sha256']))
    for key,row in state['frozen_build38'].items():
        assert sha(HERE/row['record_file'])==row['record_sha256'], ('Frozen build input changed',key)
    receipt=dict(label='电脑预测及记录一致性',baseline_registry_sha256=state['baseline_candidate_registry_sha256'],
        changed_records=changes,changed_count=len(changes),unchanged_count=105-len(changes),
        frozen_build38_old_paths_and_bytes_preserved=True,
        source_checkpoint=state['checkpoint'])
    atomic_bytes(HERE/'record_sha_changes.json',(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n').encode())
    registry['record_sha_changes_sha256']=sha(HERE/'record_sha_changes.json')
    registry['frozen_build38_old_paths_and_bytes_preserved']=True


def build_list_fields(rows,profiles):
    lookup={(r['unit'],r['index']):r for r in profiles}
    for unit,items in rows['units'].items():
        for item in items['not_replaced']:
            source=lookup[unit,item['index']]
            if source.get('deployment_action')=='keep_current':
                item.update(deployment_action='keep_current',
                    deployment_record_file=source['deployment_record_file'],
                    deployment_record_sha256=source['deployment_record_sha256'],
                    reason=source['build_block_reason'])
