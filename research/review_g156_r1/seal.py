"""Freeze the Chinese review and bind all inputs and evidence to SHA256SUMS."""
from pathlib import Path
import datetime as dt
import json
import subprocess
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import common as C
C.setup()

def read(name):return json.loads((C.HERE/'evidence'/name).read_text())
for name in ('static.json','parsers.json','instructions.json','receipt_audit.json','history.json','runtime_samples.json'):
    assert read(name)['status']=='PASS',name
static=read('static.json');receipts=read('receipt_audit.json')['rows'];samples=read('runtime_samples.json')['rows']
assert len(receipts)==9 and len(samples)==4
assert {x['label']for x in samples}=={'review-release-50mm-native','review-release-bw-close-native','review-old-g155c-native','review-old-g155c-reference'}
assert all(x['status']=='PASS'for x in receipts+samples)

frozen_by_path={r['path']:r for r in read('frozen_inputs.json')['files']}
for row in read('initial_inputs.json')['inputs']:frozen_by_path[row['path']]=row
for row in json.loads((C.HERE/'evidence/g155c_saved_records.json').read_text()):
    frozen_by_path[row['path']]=dict(path=row['path'],sha256=row['sha256'])
frozen=list(frozen_by_path.values());drift=[]
for info in frozen:
    path=C.ROOT/info['path']
    if not path.is_file()or C.sha(path.read_bytes())!=info['sha256']:drift.append(info['path'])
assert not drift,('frozen inputs changed',drift)
for row in read('records.json')['rows']:
    if row['action']=='replace':
        path=C.RECORDS/row['registry_file']
        assert C.sha(path.read_bytes())==row['registry_sha256']
checks=[]
for sums in [*(folder/'SHA256SUMS'for folder in C.PACKAGES.values()),C.ORIGINAL/'SHA256SUMS']:
    count=0
    checksum_root=sums.parent if sums.parent in C.PACKAGES.values() else C.ROOT
    for line in sums.read_text().splitlines():
        if not line.strip():continue
        digest,name=line.split('  ',1);path=checksum_root/name
        assert path.resolve().is_relative_to(C.ROOT) and C.sha(path.read_bytes())==digest,(str(sums),name)
        count+=1
    checks.append(dict(path=str(sums.relative_to(C.ROOT)),sha256=C.sha(sums.read_bytes()),files=count,status='PASS'))
head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
assert head==read('initial_inputs.json')['head']
now=dt.datetime.now(dt.timezone.utc)
start=dt.datetime(2026,11,3,18,36,13,tzinfo=dt.timezone.utc)
minutes=(now-start).total_seconds()/60
assert minutes<=150,('time box exceeded',minutes)
C.save(C.HERE/'evidence/final_freeze.json',dict(status='PASS',frozen_files=len(frozen),changed=drift,
    frozen_manifest_sha256=C.sha((C.HERE/'evidence/frozen_inputs.json').read_bytes()),
    head=head,verified_utc=now.isoformat(),original_checksum_manifests=checks))

reference_table=['| 包 / 单元 / 类型 | 回执后端 | 记录或恢复目标 | 独立核对 |',
                 '| --- | --- | --- | --- |']
for row in receipts:
    name=Path(row['receipt']).name
    target='、'.join(row['records'])if not row['restore']else'非零 '+str(row['levels'])
    kind='恢复'if row['restore']else'正常流程'
    reference_table.append('| '+row['profile']+' / '+row['unit']+' / '+kind+' | '+row['backend']+' | '+target+' | [PASS](../g156/evidence/'+name+') |')
sample_table=['| 抽样 | 后端 | 结果与实际范围 |', '| --- | --- | --- |']
for row in samples:
    name=Path(row['receipt']).name
    if row.get('old_record_clean_reject'):
        detail='旧记录干净拒绝；完整原生 04；W=0；记录 40 B 保留'
    elif row.get('each_recipe_both_closes'):
        detail='03 HC BW、Tri-X 400 各自 OK/ADJ 关闭，重开后完整 552 B 保持'
    else:
        detail='七条 release/50mm 换入项的完整读回、光标、DISP、OK/ADJ，W 范围通过'
    sample_table.append('| ['+row['label']+'](evidence/'+name+') | '+row['backend']+' | PASS，'+detail+' |')
release=next(r for r in static['packages']if r['profile']=='release')
collision=next(r for r in release['old_index_collisions']if r['unit']=='a12-50'and r['old_name']=='Tri-X 400')
collision_text=('例如 g155c 的 a12-50 索引 `'+collision['record_index']+'` 原来表示 '+collision['old_name']+
                '，在 g156 release 的全局 Look 表中已经表示 '+collision['new_name'])
values={'SEALED_UTC':now.isoformat(),'MINUTES':f'{minutes:.1f}',
        'COLLISION':collision_text,'REFERENCE_TABLE':'\n'.join(reference_table),
        'SAMPLE_TABLE':'\n'.join(sample_table),
        'INTERRUPTED_KEYS':str(read('reference-normal-interrupted.json')['completed_keys']),
        'DRIFT':str(len(drift))}
report=(C.LOCAL/'REVIEW.template.md').read_text()
for key,value in values.items():report=report.replace('@@'+key+'@@',value)
assert '@@'not in report
(C.HERE/'REVIEW.md').write_text(report)

# Include existing receipt sources as data. This never restores a saved machine.
paths={C.ROOT/r['path']for r in frozen}
for row in read('records.json')['rows']:
    if row['action']=='replace':paths.add(C.RECORDS/row['registry_file'])
for folder in ['tools/native_harness','tools/native_harness_c']:
    paths.update(p for p in(C.ROOT/folder).rglob('*')if p.is_file()and p.suffix in('.py','.c','.h','.inc')and'local'not in p.relative_to(C.ROOT/folder).parts)
for name,digest in [('jlaunch3','951be1c659c85af58ae3e4ce98707c52f0b4514fc2075256854d59f822671673'),
                    ('qlaunch3','e487d00b5539aa1e3ca9373829456e00676b37310dc717f0a5bcb5235bac6690'),
                    ('l08firm3','0a4dff6d3be9b9a9b56dfcbd98a2df59efcb31f7d4eaca6b0c3fbdb1641fde44')]:
    path=C.ROOT/'artifacts/firmware/gxr-1.51'/name
    assert C.sha(path.read_bytes())==digest
    paths.add(path)
def collect(value):
    if isinstance(value,dict):
        for v in value.values():collect(v)
    elif isinstance(value,list):
        for v in value:collect(v)
    elif isinstance(value,str):
        if value.startswith(('firmware/','research/','tools/','studio/','artifacts/')):
            path=C.ROOT/value
        elif value.startswith(str(C.ROOT)+'/'):
            path=Path(value)
        else:return
        if path.is_file()and path.resolve().is_relative_to(C.ROOT):paths.add(path)
for row in receipts:
    path=C.ROOT/row['receipt'];collect(json.loads(path.read_text()))
    d=json.loads(path.read_text())
    if d.get('cold_receipt'):
        cold=C.ROOT/d['cold_receipt'];paths.add(cold.with_name(cold.stem+'-detail.json'))
for path in (C.HERE/'evidence').glob('*.json'):collect(json.loads(path.read_text()))
paths.update(p for p in C.HERE.rglob('*')if p.is_file()and p.name not in ('SHA256SUMS','seal_receipt.json'))
paths={p for p in paths if p.is_file()}
text=''.join(C.sha(p.read_bytes())+'  '+str(p.relative_to(C.ROOT))+'\n'for p in sorted(paths))
(C.HERE/'SHA256SUMS').write_text(text)
for line in text.splitlines():
    digest,name=line.split('  ',1)
    assert C.sha((C.ROOT/name).read_bytes())==digest,name
C.save(C.HERE/'seal_receipt.json',dict(status='PASS',release='可以上卡',test='可以上卡',
    scope='Specified DATs only; supervised field test after approved body v3.10 flash and no-DAT camera check',
    sealed_utc=now.isoformat(),elapsed_minutes=minutes,frozen_input_files=len(frozen),frozen_drift=drift,
    checksum_files=len(paths),SHA256SUMS_sha256=C.sha(text.encode()),REVIEW_sha256=C.sha(report.encode()),
    original_checksum_manifests=checks,all_checksum_entries_verified=True,
    expected_exclusions=['SHA256SUMS self hash','seal_receipt.json self hash']))
print(json.dumps(dict(status='PASS',files=len(paths),minutes=round(minutes,1),verdict='可以上卡（release）；可以上卡（test）'),ensure_ascii=False))
