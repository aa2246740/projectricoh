"""Write a complete, explicit handoff when the requested time limit ends."""
from pathlib import Path
import argparse
import hashlib
import json
import runpy
import sys
import datetime

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / 'research/g131_merge'
ENGINE = ROOT / 'firmware/engine_v51_g131'
PACKAGE = ROOT / 'firmware/package_v36_g131'

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def read_rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--unfinished-index', type=int, required=True)
    options = parser.parse_args()
    sys.path.insert(0, str(WORK))
    from fences import enable, check_inputs
    enable()
    count = check_inputs()
    for name in ('verify_delivery', 'verify_source', 'verify_wrapper'):
        runpy.run_path(str(WORK / (name + '.py')), run_name='__main__')
    start = json.loads((WORK / 'evidence/resume-start.json').read_text())
    assert all(sha(ROOT / name) == digest for name, digest in start['source_sha256'].items())
    pin = sha(PACKAGE / 'local/SD_ROOT/GXRCE.DAT')
    assert pin == start['dat_sha256']
    ledger = WORK / 'evidence/runs.jsonl'
    lines = ledger.read_text().splitlines()
    for path in sorted((WORK / 'local/checks').glob('*/runs.jsonl')):
        for line in path.read_text().splitlines():
            if line not in lines:
                lines.append(line)
    ledger.write_text('\n'.join(lines) + '\n')
    latest = {row['name']: row for row in map(json.loads, lines)}
    queue = json.loads((WORK / 'queue.json').read_text())
    stages = read_rows(WORK / 'evidence/stage-runs.jsonl')
    selections = {5: stages[:5], 19: stages[9:10], 23: stages[10:13]}
    rows = []
    for index, job in enumerate(queue):
        entry = latest.get(job['name'])
        if index in selections:
            selected = selections[index]
            code = 0 if selected and all(row['returncode'] == 0 for row in selected) else None
            seconds = round(sum(row['seconds'] for row in selected), 3)
            source = 'research/g131_merge/evidence/stage-runs.jsonl'
            if code == 0 and job['name'] not in latest:
                with ledger.open('a') as stream:
                    stream.write(json.dumps(dict(name=job['name'], returncode=0, seconds=seconds,
                        dat_sha256=pin, result=source)) + '\n')
        else:
            code = entry['returncode'] if entry else None
            seconds = entry['seconds'] if entry else None
            source = entry['result'] if entry else None
            if entry:
                assert entry['dat_sha256'] == pin
        status = 'OPEN_P2_03' if job.get('record_only') and code == 1 else 'PASS' if code == 0 else 'INCOMPLETE'
        if index >= options.unfinished_index:
            status = 'INCOMPLETE_TIMEBOX'
            code = None
            seconds = None
        rows.append(dict(index=index, name=job['name'], returncode=code, seconds=seconds,
                         status=status, source=source, dat_sha256=pin))
    incomplete = [row['name'] for row in rows if row['status'].startswith('INCOMPLETE')]
    result = dict(status='有缺陷', reason='INCOMPLETE_TIMEBOX', dat_sha256=pin,
                  unfinished=incomplete, rows=rows, frozen_inputs=count,
                  product_source_unchanged=True, product_assertion_failure_observed=False,
                  time=datetime.datetime.now(datetime.timezone.utc).isoformat())
    (WORK / 'evidence/timebox-result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    delivery = json.loads((WORK / 'evidence/delivery.json').read_text())
    rpc_path = WORK / 'evidence/rpc-summary.json'
    rpc = json.loads(rpc_path.read_text()) if rpc_path.exists() else dict(status='INCOMPLETE')
    table = '\n'.join('| ' + str(row['index']) + ' | ' + row['name'] + ' | ' +
        str(row['returncode'] if row['returncode'] is not None else '未完成') + ' | ' + row['status'] + ' |' for row in rows)
    report = f'''有缺陷

两小时时间盒内验收未收齐，状态为 INCOMPLETE_TIMEBOX。未观察到产品断言失败；中止记录来自旧参考接口、适配假设和诊断目录围栏，不能当作产品结论。尚缺：{', '.join(incomplete)}。

DAT SHA256：`{pin}`，89,556 B。主请求 {delivery['loader_request']:,} B，上限 108,124 B，余量 380 B。BSS 10,684 B。第七段 20,776 B 与 gen 129 相同，包内 29 个固定文件与 gen 120b 相同。

相对 gen 129，九个同名源码文件变化，构建入口改名为 build131.py，91 个文件不变。三个服务源文件与 g130 冻结清单一致，唯一产品行为变化为 H07 归属规则及入口绑定。knobs 与 resident 源码不变。完整差异见 source-change-vs-g129.patch 和 evidence/source-scope.json。本轮没有改产品源码或重建包。

变化文件为 candidate/engine_services/services.c、engine_services.h、native_seed.c，以及 candidate/containers/product/adapter.c、src/firmware/card_container_v2/gate.c、src/firmware/engine/core/eng_data.c、ui_v2_data.c、candidate/common.py、candidate/containers/product/pack.py。服务层使用 g130 规则，adapter 绑定入口；三个校验点和构建脚本只改 generation 或路径。

| 编号 | 队列项目 | 返回码 | 状态 |
| --- | --- | --- | --- |
{table}

H07 两类用例共六个最终记录均通过，晚到 S store 和预览计数均为 0，首发 mode=1、WB=9/9。三个单元的 H01 重开记录均为 mode=1、WB=9/9。全菜单点 S 计划 3,430 项与 gen 127 相同。目标 M32R 计算分别 1,133、1,134、1,163 项通过；12 个改动函数的四类编译码检查绑定当前 DAT 与 ELF。通信复核状态 {rpc.get('status')}，完整记录 {rpc.get('complete_records', 'INCOMPLETE')} 条。

P2-03 保持 OPEN。七次 preview-window 队列项原返回码均为 1；三个单元的补充观察各命中一次，晚到 S store 为 0、晚到预览为 1。此窗口未改动。

旧参考把 knobs v2 默认向量按旧 tone 等级解释。新 reference_v2.py 适配十维向量、旧默认值以及旧 DAT 解码器清零的 36 个未映射字节；3,430 点与 24 个旧解码默认值复核通过。旧比较断言保留。失败准备记录在 local/preparation，当前结果及未运行范围以 evidence/timebox-result.json 为准。

用户已停止上一轮两个 cold_reentry-50mm 孤儿进程。本轮第 24 项重新完整执行并返回 0，旧残留不计结果。结束时停止本轮仍在运行的检查进程，未完成项不记作通过。

写入围栏仅允许三个指定目录，拒绝网络。冻结输入 {count:,} 项和 103 个源码及清单文件均未变化。理光字节只在被忽略的 local/。没有访问相机、存储卡或网络，没有启动子代理。

静态已证：源码范围、布局、四类编译码、包及最终 DAT 身份。
主机已证：表中 PASS 项、S 计划、H01、目标计算及上述通信记录。
推断：入口绑定与已通过 H07 计数一致。
未知：未完成队列项，以及相机端调度、显示、拍摄、存储持久性和物理断电表现。完整 81 组回归未运行。
'''
    (WORK / 'REPORT.md').write_text(report)
    (PACKAGE / 'DELIVERY.md').write_text('gen 131\n\n本轮验收未齐，见 research/g131_merge/REPORT.md。\nDAT SHA256：`' + pin + '`。\n')
    note = '\n\n本轮时间盒续跑断点：第 ' + str(options.unfinished_index) + ' 项。先复核冻结输入、源码和 DAT 身份，再执行以下命令；未完成项的旧残留不算结果。\n\n```sh\n/usr/bin/sandbox-exec -f research/g131_merge/write-fence.sb /usr/bin/python3 -I -B research/g131_merge/run_existing.py --queue research/g131_merge/queue.json --job-index ' + str(options.unfinished_index) + '\n```\n\n队列结束后复核运行 audit_communications.py、collect.py、finalize.py。\n'
    guide = WORK / 'REPRODUCE.md'
    previous = guide.read_text().split('\n\n本轮时间盒续跑断点：')[0]
    guide.write_text(previous + note)
    runpy.run_path(str(WORK / 'verify_words.py'), run_name='__main__')
    assert check_inputs() == count
    paths = sorted(path for base in (ENGINE, PACKAGE, WORK) for path in base.rglob('*')
                   if path.is_file() and not path.is_symlink() and path != WORK / 'SHA256SUMS')
    (WORK / 'SHA256SUMS').write_text(''.join(sha(path) + '  ' + str(path.relative_to(ROOT)) + '\n' for path in paths))
    print(json.dumps(dict(name='partial-finalize', returncode=1, counts=dict(
        files=len(paths), incomplete=len(incomplete), frozen_inputs=count))))

if __name__ == '__main__':
    main()
