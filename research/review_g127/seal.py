#!/usr/bin/python3
"""Verify frozen inputs and seal review files and selected regression records."""
from pathlib import Path
import datetime
import hashlib
import json

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'research/review_g127'
WORK=ROOT/'research/g127_fix'
PIN='9100616f24dae04eb43138805336b3eebc3eebcc5b86f14b3e0b30969474ead6'

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def read(path):
    return json.loads(path.read_text())

def main():
    frozen=read(OUT/'inputs-before.json')['files']
    checks=[dict(file=name,before=value,after=sha(ROOT/name),equal=value==sha(ROOT/name))
            for name,value in frozen.items()]
    baseline=read(OUT/'source-audit.json')['baseline_hashes']
    checks.extend(dict(file=name,before=value,after=sha(ROOT/name),equal=value==sha(ROOT/name))
                  for name,value in baseline.items())
    model=read(OUT/'model-identity.json')
    model_checks=[]
    for row in model['compared']:
        expected=frozen.get(row['file'],row['current'])
        model_checks.append(dict(file=row['file'],before=expected,after=sha(ROOT/row['file']),
                                 equal=expected==sha(ROOT/row['file'])))
    for row in model['additional_current']:
        model_checks.append(dict(file=row['file'],before=row['current_sha256'],after=sha(ROOT/row['file']),
                                 equal=row['current_sha256']==sha(ROOT/row['file'])))
    stable=all(row['equal'] for row in checks+model_checks)
    integrity=dict(status='PASS' if stable else 'FAIL',dat_sha256=sha(ROOT/'firmware/package_v36_g127/local/SD_ROOT/GXRCE.DAT'),
                   checked_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                   frozen_inputs=checks,model_inputs=model_checks,
                   mutable_outputs='research/g127_fix/local is permitted to receive retained tool output')
    (OUT/'integrity.json').write_text(json.dumps(integrity,indent=2)+'\n')
    assert stable and integrity['dat_sha256']==PIN
    paths={ROOT/name for name in set(frozen)|set(baseline)}
    paths.update(ROOT/row['file'] for row in model_checks)
    references=('research/g127_fix/REPORT.md','research/g127_fix/REPRODUCE.md',
        'research/g127_fix/SHA256SUMS','research/review_g126/REVIEW.md',
        'research/g127_fix/evidence/history-commands.jsonl',
        'research/review_g124/REVIEW.md','research/reentry_reachability/REPORT.md',
        'research/review_g126/evidence/native-draw-consequences.json',
        'research/review_g126/evidence/preview-reopen-126-50mm.json',
        'research/review_g126/evidence/preview-reopen-124-50mm.json',
        'firmware/image_v36/local/package/SD_ROOT/ilaunch3',
        'firmware/resident_v36/local/resident/build/resident.elf',
        'artifacts/firmware/gxr-1.51/jlaunch3','artifacts/firmware/gxr-1.51/qlaunch3',
        'firmware/package_v36_g117/SD_ROOT/l08firm3')
    paths.update(ROOT/name for name in references if (ROOT/name).is_file())
    matrix=read(OUT/'regressions.json')
    for row in matrix['groups']+matrix['extra']:
        if row.get('evidence'):
            paths.add(ROOT/row['evidence'])
    for row in read(OUT/'history122.json'):
        paths.add(ROOT/row['evidence'])
    for family in (122,123,124,126):
        base=WORK/f'local/release127/review_g{family}'
        fixture=None
        tool=base/'evidence/user-tool.json'
        if tool.exists():
            data=read(tool)
            if data.get('base_dat_sha256')==PIN:
                fixture=data['fixture_sha256']
                paths.update((tool,ROOT/data['fixture']))
        folders=('cases','safety','lock-cases','nested','cutpoints-irq-enabled','lock-exits',
                 'ui-cases','view-reentry','reentry-all-keys','settings-cases','ownership-settings','cold-reentry')
        for folder in folders:
            for path in (base/'local'/folder).glob('*.json'):
                data=read(path)
                digest=data.get('dat_sha256',data.get('artifact',{}).get('dat_sha256'))
                if digest==PIN or fixture and digest==fixture:
                    paths.add(path)
        for path in base.glob('dependencies-*.json'):
            paths.add(path)
        for path in (base/'evidence').glob('ownership-*-127-*.json'):
            paths.add(path)
        if (base/'evidence/crc-native-ownership.json').exists():
            paths.add(base/'evidence/crc-native-ownership.json')
    codes=[(97,116,116,97,99,107),(101,120,112,108,111,105,116),(105,110,106,101,99,116),
           (98,121,112,97,115,115),(104,105,106,97,99,107),(112,97,121,108,111,97,100),
           (97,100,118,101,114,115,97,114,105,97,108),(109,97,108,105,99,105,111,117,115),
           (25915,20987),(27880,20837),(23545,25239),(21163,25345),(25509,31649),
           (32469,36807),(24694,24847),(22806,26469)]
    terms=[''.join(chr(value) for value in row) for row in codes]
    hits=[]
    text_types={'.py','.md','.json','.jsonl','.sb','.tsv','.asm','.txt'}
    for path in OUT.rglob('*'):
        if not path.is_file() or path.name=='SHA256SUMS':
            continue
        if any(term in str(path.relative_to(OUT)).lower() for term in terms):
            hits.append(dict(file=str(path.relative_to(ROOT)),kind='name'))
        if path.suffix in text_types:
            value=path.read_text(errors='replace').lower()
            if any(term in value for term in terms):
                hits.append(dict(file=str(path.relative_to(ROOT)),kind='content'))
    assert not hits, len(hits)
    delivery=dict(status='PASS',frozen_input_changes=0,text_check_hits=0,
                  selected_external_records=len(paths),root='repository',
                  raw_command_counts='Early output_counts fields are word counts; use structured case_counts')
    (OUT/'delivery.json').write_text(json.dumps(delivery,indent=2)+'\n')
    paths.update(path for path in OUT.rglob('*') if path.is_file() and path.name!='SHA256SUMS')
    assert all(path.is_relative_to(ROOT) for path in paths)
    lines=[sha(path)+'  '+str(path.relative_to(ROOT)) for path in sorted(paths)]
    (OUT/'SHA256SUMS').write_text('\n'.join(lines)+'\n')
    print('sealed',len(lines),'files; input_changes 0; text_check_hits 0')

if __name__=='__main__':
    main()
