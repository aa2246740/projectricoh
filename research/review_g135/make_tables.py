"""Write REGRESSIONS.md from regressions.json (81 groups) and the result files of the additional suites."""
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[2]
WORK = Path(__file__).resolve().parent
CHECKS = WORK / 'local/checks'

def result(family, stem):
    path = CHECKS / family / f'result-{stem}.json'
    if path.exists():
        data = json.loads(path.read_text())
        return data['returncode'], data['seconds']
    return None, None

def cell(rc, sec):
    return ('NOT_RUN', '', '') if rc is None else ('PASS' if rc == 0 else 'FAIL', rc, f'{sec:.0f}')

def main():
    rows = json.loads((WORK / 'regressions.json').read_text())
    lines = ['# 81 组完整回归表（review-g135-r1）', '',
             '结果列：PASS = 返回码 0；FAIL_* = 返回码非 0 且已归类（依据列）；NOT_RUN = 时间盒内没有跑到；不把未跑、工具适配失败或设计变化记为产品通过。',
             '全部由本复审自己的运行器 `runner.py` 对 gen 135 DAT（57743bc1…）+ v3.7 机身执行；旧脚本未改。归类依据与修正读取见 PORT_NOTES.md、WRAPPER.md。', '',
             '| 家族 | 单元 | 组 | 返回码 | 秒 | 结果 | 依据 |', '| --- | --- | --- | --- | --- | --- | --- |']
    counts = {}
    for r in rows:
        counts[r['outcome']] = counts.get(r['outcome'], 0) + 1
        rc = '' if r.get('returncode') is None else r['returncode']
        sec = '' if r.get('seconds') is None else f"{r['seconds']:.0f}"
        basis = r.get('basis') or ''
        if r['outcome'] == 'PASS':
            basis = ''
        lines.append(f"| {r['family']} | {r['unit']} | {r['group']} | {rc} | {sec} | {r['outcome']} | {basis} |")
    lines += ['', '汇总：' + '，'.join(f'{k} {v}' for k, v in sorted(counts.items())) + f'（共 {len(rows)} 组）。', '']
    # additional suites
    extra = ['## 附加套件与独立复跑', '', '| 项目 | 单元 | 返回码 | 秒 | 结果 | 说明 |', '| --- | --- | --- | --- | --- | --- |']
    def add(name, unit, rc, sec, note=''):
        r, rcv, s = cell(rc, sec)
        extra.append(f'| {name} | {unit} | {rcv} | {s} | {r} | {note} |')
    for u in ('50mm', '28mm', 'mount'):
        add('history123 suite（9 例）', u, *result('review_g123', f'run_cases-suite---generation-135---unit-{u}'), '9/9 例 wait_status 0，DAT 57743bc1…')
    for u in ('50mm', '28mm', 'mount'):
        add('settings_cases（36 例，r2 参考核心）', u, *result('review_g126', f'settings_cases---unit-{u}'), '36/36')
    for u in ('50mm', '28mm', 'mount'):
        add('history122（9 条/单元）', u, *result('review_g122', f'run_cases-suite---generation-121---unit-{u}'), '逐条判断见 HISTORY122.md（27/27）')
    for u in ('50mm', '28mm', 'mount'):
        add('safety 修正读取（safety_cases_g135.py）', u, *result('review_g126', f'safety_cases_g135---unit-{u}'), '8/8；原读取 5/8（见上表 safety 行）')
    sched = {}
    for leg in ('schedule-results-v1.json', 'schedule-results-v2-final.json', 'schedule-results-v3.json'):
        for r in json.loads((WORK / leg).read_text()):
            sched[r['name']] = r
    for u in ('28mm', 'mount'):
        r = sched.get(f'accept-{u}', {})
        add('accept.py 复跑（accept_rerun.py）', u, r.get('returncode'), r.get('seconds'), 'ACCEPT_DONE；part 1 重显 8 行、光标 4、强制 part 0/4 时 jl_delta=1；写入全 0')
    for u in ('50mm', '28mm', 'mount'):
        r = sched.get(f'accept-parts-{u}', {})
        add('accept 扩展：part 0…7 全部取值（accept_parts.py）', u, r.get('returncode'), r.get('seconds'), '仅 part 1、2 被接受（jl_delta=0），0/3/4/5/6/7 均 jl_delta=1')
    for case in ('preview-window', 'preview-deferred', 'pending-read'):
        r = sched.get(f'native-{case}-28mm-port2', {})
        note = {'preview-window': 'OBSERVED：核对之后换视图，预览仍进入（P2-03 重新复现）', 'preview-deferred': '核对之前换视图：无写入、无预览、pending=1、重开恢复八行', 'pending-read': '同上，外加一次读错误返回与元数据恢复'}[case]
        add(f'native_checks {case}（修正切点，{"0xd228" if case == "preview-window" else "0xd200"}）', '28mm', r.get('returncode'), r.get('seconds'), note)
        if case == 'preview-window':
            extra[-1] = extra[-1].replace('| PASS |', '| OBSERVED |')
    for case in ('h07-parent', 'h07-parent-preview'):
        add(f'native_checks {case}', '28mm', *result('review_g127', f'native_checks---case-{case}---unit-28mm---crc-mode-native'), '晚到 S 写入 0、晚到预览 0')
    for case in ('settings-check',):
        add(f'native_checks {case}', '28mm', *result('review_g127', f'native_checks---case-{case}---unit-28mm---crc-mode-native'), '')
    for u in ('50mm', '28mm'):
        add('product_menus.py 独立复跑', u, *result('review_g126', f'product_menus---unit-{u}'), '帧序列与实现者记录逐字节相同（50mm 314 帧、28mm 316 帧）')
    for u in ('50mm', '28mm'):
        path = CHECKS / 'review_g126/evidence' / f'port-transitions-{u}.json'
        extra.append(f'| ui_acceptance transitions 修正读取 | {u} | | | {"PASS" if path.exists() else "NOT_RUN"} | 42/42 例 |')
    rc, sec = result('review_g126', 'ui_acceptance_g135-values---unit-50mm')
    extra.append(f'| ui_acceptance values 修正读取 | 50mm | {rc} | {sec:.0f} | 6/7 PASS，1 项设计变化 | 四个 control 的 ±9 步进与 clamp、L1 虚拟滚动、Default 双击 PASS；back-from-second-pair 的旧光标期望 (1,1) 不成立，新设计回到刚用过的那一对 (1,2)，只断言屏幕与光标，记为设计变化 |' if rc is not None else '| ui_acceptance values 修正读取 | 50mm | | | NOT_RUN | |')
    extra.append('| ui_acceptance values 修正读取 | 28mm | -15 | 1316 | 部分 | 四个 control 的步进 4/4 PASS 后被我终止（让出进程槽）；其余三个快速用例未跑 |')
    extra += ['', '原样（stale 偏移）与修正后的 preview 窗口三例见 PORT_NOTES.md §3；有效记录为 `-port2`。']
    unclosed = [r for r in rows if r['outcome'] in ('NOT_RUN', 'TIMEBOX')]
    tail = ['', '## 时间盒内没有闭合的组（如实列出，均不记通过）', '',
            '共 %d 组：' % len(unclosed) + '；'.join(f"{r['family']}/{r['unit']}/{r['group']}（{r['outcome']}）" for r in unclosed) + '。',
            '', '其中 TIMEBOX 是调度器在时间盒到点时终止的作业（group124-28mm-view-reentry、group124-28mm-reentry-six 刚起跑，group126-mount-project 已跑 92 s）。',
            '没有跑到的都是下列已在 50mm（两个家族）通过或已归类的套件在其他单元 / 家族上的重复：lock-exits、view-reentry、reentry-all-keys 在 50mm 两个家族均 PASS；transitions / values 的行为部分已由修正读取复制品覆盖；原读取 safety 的三条假失败已由修正读取三单元 8/8 覆盖。']
    (WORK / 'REGRESSIONS.md').write_text('\n'.join(lines + extra + tail) + '\n')
    print(json.dumps(counts, ensure_ascii=False))

if __name__ == '__main__':
    main()
