#!/usr/bin/python3
"""Keep supplemental command results separate from firmware acceptance."""
from pathlib import Path
import collections
import json

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'research/review_g127'

def read(path, default):
    return json.loads(path.read_text()) if path.exists() else default

def main():
    commands=[]
    for line in (OUT/'runs.jsonl').read_text().splitlines():
        row=json.loads(line)
        if row.get('kind') in ('native','crc'):
            commands.append(dict(name=row['name'],returncode=row['returncode'],seconds=row['seconds'],
                                 expected=0,source='initial',status='ENDED' if row['returncode']==0 else 'SETUP_ERROR'))
    priority=read(OUT/'priority.json',{})
    if priority:
        commands.append(dict(name=priority['name'],returncode=priority['returncode'],
                             seconds=priority['seconds'],expected=0,source='priority',status='ENDED'))
    for row in read(OUT/'additional.json',[]):
        commands.append({key:row.get(key) for key in ('name','returncode','seconds','expected','status')})
        commands[-1]['source']='additional'
    evidence=[]
    for path in sorted((OUT/'evidence').glob('*.json')):
        data=read(path,{})
        if 'before' in data and 'after' in data and data.get('status') in ('PASS','OBSERVED'):
            evidence.append(dict(name=path.stem,status=data['status'],
                late_settings=len(data.get('settings_stores_after_switch',[])),
                late_preview=len(data.get('preview_entries',[])),
                pending_after=data['after'].get('pending'),
                pending_reopened=data.get('reopened',{}).get('pending'),
                evidence=str(path.relative_to(ROOT))))
    value=dict(commands=commands,evidence=evidence,
        command_counts=dict(collections.Counter(row['status'] for row in commands)),
        note='Expected control exits and observed timing cases are separate from firmware PASS.')
    (OUT/'controls.json').write_text(json.dumps(value,indent=2)+'\n')
    lines=['补充命令结果。ENDED 只表示命令正常结束；切点记录的 OBSERVED 另表列出。',
        'SETUP_ERROR 是 mount 映像登记遗漏的早期前置错误，修正后的 repeat 命令单列。',
        '两个 expected=1 的控制用于证实断言仍执行以及 ASCII 上限变化，符合预期时不计固件失败。',
        '', '| 命令组 | 来源 | 预期返回码 | 实际返回码 | 秒 | 命令结果 |',
        '| --- | --- | --- | --- | --- | --- |']
    for row in commands:
        lines.append(f"| {row['name']} | {row['source']} | {row['expected']} | {row['returncode']} | {row['seconds']} | {row['status']} |")
    lines += ['', '| 证据 | 状态 | 晚到 S store | 晚到预览 | 返回 pending | 重开 pending |',
              '| --- | --- | --- | --- | --- | --- |']
    for row in evidence:
        lines.append(f"| {row['name']} | {row['status']} | {row['late_settings']} | {row['late_preview']} | {row['pending_after']} | {row['pending_reopened']} |")
    (OUT/'CONTROLS.md').write_text('\n'.join(lines)+'\n')
    print('controls',len(commands),'records',len(evidence))

if __name__=='__main__':
    main()
