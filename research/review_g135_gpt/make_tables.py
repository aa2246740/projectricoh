from pathlib import Path
import collections
import json

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'research/review_g135_gpt'
prior = json.loads((ROOT / 'research/review_g135/regressions.json').read_text())
plan = json.loads((OUT / 'queue.json').read_text())
state_file = OUT / 'evidence/scheduler.json'
active = set(json.loads(state_file.read_text()).get('active', [])) if state_file.exists() else set()
recovery_file = OUT / 'evidence/recovered-groups.json'
recovered = json.loads(recovery_file.read_text()) if recovery_file.exists() else {}
decisions_file = OUT / 'evidence/classification-decisions.json'
decisions = json.loads(decisions_file.read_text()) if decisions_file.exists() else {}
jobs = collections.defaultdict(list)
for job in plan['jobs']:
    jobs[job.get('covers', job['name'])].append(job)


def current(name):
    attempts = []
    for job in jobs[name]:
        path = OUT / 'local/jobs' / job['name'] / 'execution.json'
        if path.exists():
            data = json.loads(path.read_text())
            attempts.append((data['utc'], job, data))
        elif job['name'] in recovered:
            data = recovered[job['name']]
            attempts.append((data['utc'], job, data))
    if not attempts:
        return None
    stamp, job, data = max(attempts)
    data = dict(data, job=job['name'], script=next((arg for arg in job['args'] if arg.endswith('.py')), job.get('driver', 'bridge.py')))
    return data


rows = []
for old in prior:
    row = {key: old[key] for key in ['name', 'family', 'unit', 'group', 'outcome']}
    row['first_returncode'] = old.get('returncode')
    row['current'] = current(old['name'])
    if row['current'] is None:
        row['current_outcome'] = ('沿用已校验的首轮证据' if old['outcome'] == 'PASS' else 'RUNNING' if any(job['name'] in active for job in jobs[old['name']]) else 'NOT_STARTED' if jobs[old['name']] else '未独立重跑')
    elif row['current']['execution'] != 'FINISHED':
        row['current_outcome'] = row['current']['execution']
    elif row['current']['returncode'] == 0:
        row['current_outcome'] = 'PASS'
    else:
        row['current_outcome'] = '待核对'
    if old['name'] in decisions:
        row['current_outcome'] = decisions[old['name']]['outcome']
        row['decision'] = decisions[old['name']]
    if row['current'] and row['current']['execution'] == 'RECOVERED_REPORT':
        row['current_outcome'] = '子项结果已复原，退出回执未留存'
    rows.append(row)
(OUT / 'regressions.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2) + '\n')
pending_before = [row for row in rows if row['outcome'] in ['NOT_RUN', 'TIMEBOX']]
user_rows = [row for row in rows if row['outcome'] == 'TOOL_PREREQ']
closed_names = {'PASS', '旧入口已归类，替代检查通过', '旧光标期望已归类，其余通过'}
user_known = '卡片标题差异已记录，其余断言完成'
summary = {'total_original_groups': len(rows), 'remaining_from_first_review': 27, 'remaining_closed': sum(row['current_outcome'] in closed_names for row in pending_before), 'remaining_unresolved': [row['name'] for row in pending_before if row['current_outcome'] not in closed_names], 'users_total': len(user_rows), 'users_passed': sum(row['current_outcome'] == 'PASS' for row in user_rows), 'users_checked': sum(row['current_outcome'] in ['PASS', user_known] for row in user_rows), 'users_known_differences': [row['name'] for row in user_rows if row['current_outcome'] == user_known], 'users_unresolved': [row['name'] for row in user_rows if row['current_outcome'] not in ['PASS', user_known]], 'new_passes': sum(row['current_outcome'] == 'PASS' for row in rows)}
summary['remaining_recovered_reports'] = [row['name'] for row in pending_before if row['current'] and row['current']['execution'] == 'RECOVERED_REPORT']
summary['remaining_not_started'] = [row['name'] for row in pending_before if row['current_outcome'] == 'NOT_STARTED']
(OUT / 'evidence/regression-summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n')
lines = ['# 回归表', '', '原始 81 组逐项保留。PASS 指本轮实际返回 0；沿用项只表示首轮记录及清单已核对。旧断言失效的组保留原返回码，替代检查不改写成原组通过。RECOVERED_REPORT 表示完整子项报告已复原，但没有外层进程退出回执；不计严格闭合。其秒数来自末份报告时间戳与启动记录之差。', '', '| 家族 | 单元 | 组 | 首轮 | 本轮 | 退出回执 | 执行状态 | 秒 | 实际脚本 / 证据 |', '| --- | --- | --- | --- | --- | --- | --- | --- | --- |']
for row in rows:
    data = row['current']
    evidence = data['script'] + '；local/jobs/' + data['job'] + '/' if data else ''
    receipt = ('未留存；运行器报告 1' if data and data['execution'] == 'RECOVERED_REPORT' else data['returncode'] if data else '')
    lines.append('| ' + ' | '.join(map(str, [row['family'], row['unit'], row['group'], row['outcome'], row['current_outcome'], receipt, data['execution'] if data else 'NOT_STARTED' if jobs[row['name']] else '', data['seconds'] if data else '', evidence])) + ' |')
lines += ['', '## 首轮未闭合的 27 组', '', '闭合 ' + str(summary['remaining_closed']) + '/27。以下组仍未闭合，不能记为通过。', '']
lines += ['- ' + name + '。' for name in summary['remaining_unresolved']] or ['本轮没有剩余未闭合组。']
lines += ['', '其中三组值域报告见 evidence/recovered-groups.json：每组四个逐档检查、L1 滚动与 Default 通过；返回第二行的旧期望失败，实际为 (1,2)，符合 DESIGN.md 的分层光标记忆。缺少退出回执，仍列在未闭合项内。'] if recovered else []
lines += ['', '## 用户条目', '', '本轮执行闭合 ' + str(summary['users_checked']) + '/9，通过 ' + str(summary['users_passed']) + '/9，另有 ' + str(len(summary['users_known_differences'])) + ' 组保留卡片标题差异。工具检查与界面组分列；工具通过不能代替界面组。', '']
lines += ['- ' + name + ' 仍未闭合。' for name in summary['users_unresolved']]
(OUT / 'REGRESSIONS.md').write_text('\n'.join(lines) + '\n')

basis = {
    'FAIL_ORIGINAL_READ': '原 ready=2523、旧布局和旧对比度期望不适用。目标编译器复核 ready=4844、uncertain=4848、write_started=4859；修正读取保留原恢复与锁存断言，见 layout-current.json、safety 组与 g129 triage。',
    'FAIL_RETIRED_FUNCTION': '原组先查 uv_levels 即停止，尚未进入产品断言。uv_levels 的旧十一字节接口已被新点表替代；uv_window 仍在最终 ELF 的 0x250，不能称为退役。完整计算边界与实际 M32R 窗口分别补证，见 boundary-sweep.json、windows.json。',
    'TOOL_PREREQ': '原组缺少 user-tool.json，未进入产品断言。旧工具拒绝当前 DAT 外层格式。新 users_gxui.py 保留 GXUI v1 记录，工具验收已通过；本轮界面结果见回归表，原工具失败不改记产品通过。',
}
classified_lines = ['# 首轮 24 组归类的独立核对', '', '8 组旧显示、5 组旧入口、2 组旧读取、9 组工具前提，共 24 组。原错误均不能直接判作 gen 135 产品断言失败；每组的替代覆盖仍单独记账。', '', '| 家族 | 单元 | 组 | 独立判断与依据 |', '| --- | --- | --- | --- |']
for row in rows:
    if row['outcome'] not in ['FAIL_OLD_DESIGN_TEXT', 'FAIL_RETIRED_FUNCTION', 'FAIL_ORIGINAL_READ', 'TOOL_PREREQ']:
        continue
    if row['outcome'] == 'FAIL_OLD_DESIGN_TEXT':
        if row['group'] == 'transitions':
            why = '旧卡片与项目文字不符新设计，旧零位为 5，新零位为 9。新卡片显示 C/H、S/F、V/W、T/P、Amt、Default。原两个家族的函数合同相同，适配未减少断言；实际 transitions 结果见回归表。'
        elif row['group'] == 'values':
            why = '旧 ±5、十一字节向量和全零默认值不符新设计。当前四项按实际点表步进，向量为十个 int16，Amount 默认 100。返回卡片光标须保留各层记忆；旧 (1,1) 与新 (1,2) 分开记录，实际结果及导航观察见本轮证据。'
        else:
            why = '旧 03 卡片和 Shad 后为空白的断言不适用。当前三单元 03 控件精确为 [1,2,3,4,9]，即 Cont/High/Shad/Fade/Filt；Shad 后应为 Fade。隐藏 Satu 的拒绝由计算边界补证，填充与窗口规则见实际 M32R 窗口及菜单记录；原组不记 PASS。'
    else:
        why = basis[row['outcome']]
    classified_lines.append('| ' + ' | '.join(map(str, [row['family'], row['unit'], row['group'], why])) + ' |')
classified_lines += ['', '依据：`research/knobs_v2_engine_design/DESIGN.md`；`research/g129_safety_triage/REPORT.md`；本目录 `evidence/static-review.json`、`family-contracts.json`、`port-contracts.json`、`layout-current.json`、`boundary-sweep.json`、`windows.json`、`nav-memory.json` 和逐组记录。', '', '需要更正首轮说明：五组 project 停止的直接原因是 uv_levels 缺少旧入口；uv_window 保留，首轮关于两个函数都不存在的说法不成立。该说明错误属于复审证据问题，不能据此判定固件窗口故障。']
(OUT / 'CLASSIFICATION.md').write_text('\n'.join(classified_lines) + '\n')
print(json.dumps(summary, ensure_ascii=False))
