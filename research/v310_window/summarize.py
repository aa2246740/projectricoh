#!/usr/bin/python3
"""Collect exact link sizes and distinguish completed checks from the open boot gate."""
import hashlib
import json
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[2]
HERE=ROOT/'research/v310_window'
CORE=['baseline','root_shared','word_scan','aligned_reads','compiler','aligned_compiler','neutral']
UNITS=['50mm','28mm','mount']


def read(path):return json.loads(path.read_text())


def main():
    evidence=HERE/'evidence';checks={};flows=[]
    for name in CORE:
        host=read(evidence/name/'host-c.json');assert host['status']=='PASS' and host['lines']==51
        recovery=read(evidence/name/'recovery.json');assert recovery['status']=='PASS' and recovery['hook_entries']==0
        for unit in UNITS:
            data=read(evidence/name/('harness-flow-'+unit+'-c.json'));assert data['status']=='PASS'
            baseline=read(evidence/'baseline'/('harness-flow-'+unit+'-c.json'))
            left,right=dict(data['detail']),dict(baseline['detail'])
            for key in ['record','record_identity_and_crc_verified']:
                left.pop(key,None);right.pop(key,None)
            assert left==right,(name,unit)
            assert data['rpc_writes']==baseline['rpc_writes']
            assert data['native_stats']['instructions']>0
            flows.append(dict(name=name,unit=unit,full_detail_equal=True,rpc_writes_equal=True))
        for case in ['irom','fallback','identity','file-crc']:
            data=read(evidence/name/('harness-'+case+'-50mm-c.json'))
            baseline=read(evidence/'baseline'/('harness-'+case+'-50mm-c.json'))
            assert data['status']=='PASS' and data['ready']==baseline['ready']
            assert len(data['entries'])==len(baseline['entries'])
            assert data['detail']==baseline['detail']
            assert data['rpc_writes']==baseline['rpc_writes']
            assert data['files_opened']==baseline['files_opened']
        checks[name]=dict(host_groups=12,host_output_lines=51,flow_units=3,load_routes=4,recovery='PASS',cold_standby='NOT_CLOSED')
    for name in ['baseline','word_scan','neutral']:
        data=read(evidence/name/'harness-dirty-50mm-c.json')
        assert data['status']=='PASS' and data['detail']['dirty_bit_cases']==1952 and not data['entries']
    for name in ['baseline','aligned_reads']:
        data=read(evidence/name/'validation-c.json');assert data['status']=='PASS' and data['count']==451
    cold={name:read(evidence/name/'cold-incomplete.json')for name in ['baseline','neutral']}
    assert all(row['status']=='NOT_PASS' and row['state']==2 for row in cold.values())
    assert all(row['batch'] and row['mode']=='fast' and row['batch_stats']['batch-steps']>0 for row in cold.values())
    assert cold['baseline']['observed']==cold['neutral']['observed']
    card={}
    for unit in UNITS:
        data=read(evidence/'card_combined'/('harness-flow-'+unit+'-c.json'))
        baseline=read(evidence/'baseline'/('harness-flow-'+unit+'-c.json'))
        left,right=dict(data['detail']),dict(baseline['detail'])
        for key in ['record','record_identity_and_crc_verified']:
            left.pop(key,None);right.pop(key,None)
        assert data['status']=='PASS' and left==right
        assert data['detail']['record_identity_and_crc_verified']
        card[unit]='valid card flow equals baseline'
    for case in ['irom','fallback']:
        data=read(evidence/'card_combined'/('harness-'+case+'-50mm-c.json'))
        assert data['status']=='PASS' and not data['ready'] and not data['entries']
    assert read(evidence/'card_combined/recovery.json')['status']=='PASS'
    result=dict(window_verdict='需机主决定',equivalence_acceptance='INCOMPLETE',
                reason='普通冷启动尚未到达 state 5；基线和中性候选均停在 state 2。',
                core_checks=checks,flow_comparisons=flows,dirty_bit_cases_per_profile=1952,
                parser_cases=451,card_combined=card,behavior_changes_adopted=False,
                cold_observations_equal=True,cold_standby_pass=False,
                neutral_free_bytes=632,card_combined_free_bytes=1036)
    (evidence/'checks.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    rows=[]
    selected=set(CORE+['card_only','card_compiler','card_combined','one_irom_only','one_irom_combined','one_irom_tune_00'])
    for folder in sorted((HERE/'options').iterdir()):
        if not folder.is_dir():continue
        choices=[p for p in [folder/'measurement.json',folder/'failure.json']if p.exists()]
        if not choices:continue
        source=max(choices,key=lambda p:p.stat().st_mtime_ns);data=read(source)
        ok=source.name=='measurement.json' and data.get('link_ok',False)
        code=data.get('code_bytes')
        if code is None and (folder/'build/resident.map').exists():
            match=re.search(r'0x([0-9a-f]+)\s+__resident_code_end = \.',(folder/'build/resident.map').read_text())
            if match:code=int(match.group(1),16)-0x2005276c
        if ok:
            binary=folder/'build/resident.bin';raw=binary.read_bytes()
            assert len(raw)==code and hashlib.sha256(raw).hexdigest()==data['resident_sha256']
        name=folder.name
        cuts=data.get('cuts',[])
        change=('不使用任何机内 DAT'if 'card' in cuts or name.startswith('card')else
                '只使用机内 GXRCE0.DAT，不再择优或回退到 GXRCE1.DAT'if name.startswith('one_irom')else
                '减少一次 UI 分配复核'if 'ui' in cuts else '')
        scope=('占位预算'if '_plus' in name else '报告选项'if name in selected else '仅尺寸筛选')
        rows.append(dict(name=name,strict_link_ok=ok,code_bytes=code,
                         saved_bytes=8040-code if ok else None,
                         free_bytes=8060-code if code is not None else None,
                         source=str(source.relative_to(ROOT)),cuts=data.get('cuts',[]),flags=data.get('extra_flags',[]),
                         scope=scope,behavior_change=change,
                         equivalence='待机门槛未闭合'if name in CORE else '不作等价声明'))
    (HERE/'screening-index.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n')
    table=['完整尺寸筛选表','','失败行的代码数来自实际链接 map，仅用于诊断，不计有效节省。未列入报告建议的行均未取得完整等价证据。',
           '','| 方案 | 代码 B | 净省 B | 扣保留量后余 B | 严格链接 | 范围 | 行为变化 |',
           '| --- | ---: | ---: | ---: | --- | --- | --- |']
    for row in rows:
        table.append('| '+' | '.join(str(v)if v is not None else '—'for v in [row['name'],row['code_bytes'],row['saved_bytes'],row['free_bytes'],
              '通过'if row['strict_link_ok']else '拒绝',row['scope'],row['behavior_change']or '未作声明'])+' |')
    (HERE/'OPTIONS.md').write_text('\n'.join(table)+'\n')
    print(json.dumps(dict(flow_comparisons=len(flows),core_profiles=len(CORE),parser_cases=451,
                         screened_options=len(rows),cold_standby='NOT_CLOSED',window_verdict='需机主决定'),ensure_ascii=False))


if __name__=='__main__':main()
