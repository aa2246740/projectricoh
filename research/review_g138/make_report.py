"""Render the Chinese review from actual receipts and evidence."""
import argparse
from collections import Counter
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent


def read(name):
    path = OUT / name
    return json.loads(path.read_text()) if path.exists() else None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--final', action='store_true')
    args = parser.parse_args()
    regressions = read('REGRESSIONS.json')
    if args.final:
        assert regressions and regressions['final'] and regressions['completed'] == 81
        for name in ['repair-queue', 'supplemental-queue', 'audit-queue']:
            result = read('evidence/' + name + '-complete.json')
            assert result and all(row['returncode'] == 0 for row in result['results']), name
    pending = '该项补测尚在运行，不计为通过。'
    substitutions = {
        'RUN_STATE': '状态为 FINAL。' if args.final else '状态为 RUNNING。回归和补测尚未全部完成，本稿未封存。',
        'LOCK_RESULT': pending, 'RESTORE_COMPARE': pending, 'PARTIAL_BASELINE': pending,
        'MATH_RESULT': pending, 'REBUILD_RESULT': pending, 'HELD_LOCK_RESULT': pending,
        'COVERAGE_STATE': '已完成本轮执行' if args.final else 'RUNNING',
        'REGRESSION_SUMMARY': pending, 'REGRESSION_TABLE': '',
        'SUPPLEMENTAL_SUMMARY': '', 'SEAL_RESULT': '尚未封存，临时目录仍供本轮测试使用。',
    }
    trace = read('evidence/lock-trace.json')
    if trace:
        substitutions['LOCK_RESULT'] = ('实际 M32R store 观察为 ' + trace['status'] + '，' + str(len(trace['cases'])) +
            ' 个 op 2/op 5 锁状态用例。检查包括同值 store，不能只用最终 S 相同代替零写入。忙调用本体没有 S 或锁 store；测试在 IRQ 恢复后的明确模型边界让原持有者释放，以便上层结束。这不是原厂任务调度证明。')
    comparisons = []
    for unit in ['50mm', '28mm', 'mount']:
        result = read('evidence/restore-compare-' + unit + '.json')
        if result:
            comparisons.append(unit + ' ' + result['status'])
    if comparisons:
        substitutions['RESTORE_COMPARE'] = ('5 号 Cont=+1 的独立恢复与按键路径比较：' + '；'.join(comparisons) +
            '。每个已通过单元比较 S 全部 4096 B、九行全部 503 B、T 和同一 L1 显示状态，差异为零。私有调用历史和相机硬件状态不在这个逐字节比较内。')
    partial = read('evidence/partial-baseline.json')
    if partial:
        substitutions['PARTIAL_BASELINE'] = ('`partial_baseline_review.py` 另提供只差一行、其他恢复参数全部合格的模型起点；首开拒绝后，04 Default 仍以 ' +
            str(partial['unit_writes']) + ' 次 W 显示 `>4 Std` 并记住 04，OK 退出后该非 stock 行仍在。证据为 `evidence/partial-baseline.json`。')
    maths = [read('evidence/target-math-' + unit + '.json') for unit in ['50mm', '28mm', 'mount']]
    maths = [value for value in maths if value]
    if maths:
        substitutions['MATH_RESULT'] = ('最终指令派生 C 检查已完成 ' + str(sum(value['cases'] for value in maths)) +
            ' 个参考点，原解释器另复核 ' + str(sum(value['native_backend_cases'] for value in maths)) +
            ' 例。向量多重集合与当前可选点表核对一致。九行加 T 的 505 B 实际参数投影中，相邻档位重复 ' +
            str(sum(value['equal_adjacent_applied_outputs'] for value in maths)) +
            ' 组。镜像身份比较只在副本中归一化 ELF 标识的 4 B t_seen，执行 RAM 不变，逐项依据见各 identity-binding.json。它使用本轮新建模型的 RAM 和主机驱动计算入口，不能替代 RTOS 或原生菜单路径。')
    rebuilt = read('evidence/rebuild.json')
    if rebuilt:
        substitutions['REBUILD_RESULT'] = ('本轮独立重建结果为 ' + rebuilt['status'] + '，' + str(rebuilt['bytes']) +
            ' B，SHA256 `' + rebuilt['rebuilt_sha256'] + '`。新 ELF SHA256 为 `' + rebuilt['rebuilt_elf_sha256'] +
            '`，代码与新 DAT 对应。输出、服务 archive 和链接输入重定位到复审目录；最终链接参数另见 evidence/rebuild-link-audit.json。没有重建或改写机身，早期输出目录适配失败保留。')
    held = read('evidence/held-lock.json')
    if held:
        substitutions['HELD_LOCK_RESULT'] = ('独立观察到 ' + str(held['op2_attempts']) + ' 次 op 2、' + str(held['compensations']) +
            ' 次补偿、' + str(held['RPC']) + ' 次通信和 ' + str(held['unit_writes']) + ' 次单元 RAM W，最终 `' + held['state']['labels'][0] +
            '`，S store 为 ' + str(held['S_store_count']) + '，锁仍由原持有者保持。')
    if regressions:
        counts = '，'.join(key + ' ' + str(value) for key, value in sorted(regressions['counts'].items()))
        substitutions['REGRESSION_SUMMARY'] = ('已执行完整组 ' + str(regressions['completed']) + '/81。' + counts +
            '。PASS 必须同时有整组 OS 退出 0 和内层结果。旧约定失败保留原退出 1，不能改成原组通过。详见 `REGRESSIONS.json` 的所有 attempts。')
        table = (OUT / 'REGRESSIONS.md').read_text()
        start = table.index('| 家族 |')
        end = table.index('\n\n', start)
        substitutions['REGRESSION_TABLE'] = table[start:end]
    supplemental = read('evidence/supplemental-queue-complete.json')
    rpc = read('evidence/rpc-summary.json')
    additions = []
    if supplemental:
        additions.append('补充队列共 ' + str(len(supplemental['results'])) + ' 项，退出 0 为 ' +
                         str(sum(row['returncode'] == 0 for row in supplemental['results'])) + ' 项，逐项回执在 `evidence/receipts/`。')
    if rpc:
        totals = Counter()
        for group in rpc['groups']:
            totals.update(group['totals'])
        additions.append('矩阵目录的完整通信记录复核为 ' + rpc['status'] + '，按精确 DAT/用户夹具分为 ' + str(len(rpc['groups'])) +
                         ' 组，去重日志 ' + str(totals['logs']) + ' 份；X/V/W 及邻接字节检查见 `evidence/rpc-summary.json`。')
    substitutions['SUPPLEMENTAL_SUMMARY'] = '\n\n'.join(additions)
    seal = read('evidence/seal.json')
    if seal:
        substitutions['SEAL_RESULT'] = ('初始冻结输入 ' + str(seal['checked_files']) + ' 项，变更 ' +
            str(len(seal['changed'])) + ' 项。Scratch 清理结果：' + str(seal['temporary_removed']) +
            '。各项完整回执、输入比较和清理记录见 `evidence/seal.json`。未访问卡或相机；测试进程禁止联网，未作 Git 写操作。')
    text = (OUT / 'REVIEW.in.md').read_text()
    for key, value in substitutions.items():
        text = text.replace('@' + key + '@', value)
    assert '@' not in text
    if args.final:
        assert pending not in text
    (OUT / 'REVIEW.md').write_text(text)
    print(json.dumps(dict(final=args.final, bytes=len(text.encode()), verdict=text.splitlines()[0])))


if __name__ == '__main__':
    main()
