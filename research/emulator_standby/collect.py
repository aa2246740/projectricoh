#!/usr/bin/python3
"""Validate retained receipts and generate the Chinese result tables."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
OUT = HERE/'evidence'
TOOLS = ROOT/'tools/gxr_emulator_standby'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def freeze():
    files = sorted(TOOLS.glob('*.py')) + [TOOLS/'bridge.c', TOOLS/'build/libgxr_m32r.dylib']
    rows = {str(p.relative_to(ROOT)):sha(p) for p in files}
    target = OUT/'final-tool-sources.json'
    if target.exists():
        assert json.loads(target.read_text()) == rows
    else:
        target.write_text(json.dumps(rows,indent=2)+'\n')
    return rows


def pairs():
    frozen = freeze()
    rows = []
    for body in ('official','v39'):
        for unit in ('50mm','28mm','mount'):
            stem = f'{body}-{unit}-final-'
            a, b = [json.loads((OUT/(stem+suffix+'.json')).read_text()) for suffix in ('a','b')]
            for run in (a,b):
                assert run['cold_origin'] and run['first_state5'] and run['error'] is None
                assert run['stop']['reason'] == 'breakpoint' and run['state'] == 5
                assert run['pc'] == '0x202b1210'
                assert run['batch_stats']['batch-steps'] > 0 and run['nice'] >= 10
                assert 'fingerprint_error' not in run
                assert run['library_sha256'] == frozen['tools/gxr_emulator_standby/build/libgxr_m32r.dylib']
                for name,digest in run['sources'].items():
                    assert digest == frozen['tools/gxr_emulator_standby/'+name], name
                if body == 'v39':
                    assert run['image_sha256'] == '8233a1c464b29ba88cfdfce1d083b9bf652586edeb216cacf6f16cf36788b25d'
                else:
                    assert run['image_sha256'] == 'da1980e9d6f3996ede4953b8311cf0ce2abeb4bb300b6ee60a38f38e29a3cdf7'
            keys = ('steps','first_state5','state_sequence','batch_stats','full_state','unit_events','hsp_packets','hsp_replies','boot')
            equal = {key:a[key] == b[key] for key in keys}
            assert all(equal.values()), (body,unit,equal)
            rows.append(dict(body=body,unit=unit,first_state5=a['first_state5'],stop_steps=a['steps'],
                             state_sequence=a['state_sequence'],batch_stats=a['batch_stats'],
                             repeated_equal=equal,full_state_sha256=a['full_state']['sha256'],
                             model_inputs=a['model_inputs'],readiness=a['boot']['readiness'],
                             receipts=[stem+'a.json',stem+'b.json']))
    result = dict(status='PASS', cold_runs=12, pairs=rows)
    (OUT/'repeatability.json').write_text(json.dumps(result,indent=2)+'\n')
    lines = ['| 机身 | 单元 | 首次写入状态 5 | 首个状态 5 分派点 | tick | 第二次冷启动 |',
             '| --- | --- | ---: | ---: | ---: | --- |']
    for r in rows:
        lines.append(f"| {r['body']} | {r['unit']} | {r['first_state5']['step']:,} | {r['stop_steps']:,} | {r['first_state5']['tick']} | 完整状态与批处理统计相同 |")
    lines += ['', '| 机身与单元 | 状态 | 步数 | tick |', '| --- | ---: | ---: | ---: |']
    for r in rows:
        for s in r['state_sequence']:
            tick = s['tick'] if s['tick'] is not None else '未初始化'
            lines.append(f"| {r['body']} {r['unit']} | {s['state']} | {s['step']:,} | {tick} |")
    lines += ['', '| 机身与单元 | batches | batch-steps | slow-breakpoint | exit-deadline | exit-irq |',
              '| --- | ---: | ---: | ---: | ---: | ---: |']
    for r in rows:
        s = r['batch_stats']
        values = ' | '.join(f'{s.get(k,0):,}' for k in ('batches','batch-steps','slow-breakpoint','exit-deadline','exit-irq'))
        lines.append(f"| {r['body']} {r['unit']} | {values} |")
    (HERE/'RESULT_TABLES.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps(dict(status='PASS',cold_runs=12,pairs=len(rows))))


def compatibility():
    results = []
    for case in ('window','recovery'):
        a,b = [json.loads((OUT/f'{case}-{emu}-{case}-final.json').read_text()) for emu in ('batch','standby')]
        keys = ('full_state','batch_stats')
        if case == 'window':
            keys += ('stop','state','observed','board_events','dma_lengths','ready_notifications_released')
            assert all(a['historical_equal'].values()) and all(b['historical_equal'].values())
        else:
            keys += ('steps','stop','counts','milestones','nand_commands','hooks_or_resident_executed')
            assert a['steps'] == b['steps'] == 65_975_242
            assert a['card']['sha256'] == b['card']['sha256']
        equal = {k:a[k] == b[k] for k in keys}
        assert all(equal.values()), (case,equal)
        results.append(dict(case=case,equal=equal,full_state_sha256=a['full_state']['sha256']))
    (OUT/'model-off-comparison.json').write_text(json.dumps(dict(status='PASS',results=results),indent=2)+'\n')
    print(json.dumps(dict(status='PASS',cases=len(results))))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('freeze','pairs','compatibility'))
    args = parser.parse_args()
    {'freeze':freeze,'pairs':pairs,'compatibility':compatibility}[args.command]()
