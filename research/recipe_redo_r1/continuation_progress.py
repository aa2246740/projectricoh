"""Write continuation checkpoints from saved per-profile receipts."""
from pathlib import Path
import collections
import datetime
import json
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from capabilities import main_level,mount_l1_enabled

HERE = Path(__file__).resolve().parent
UNITS = ('mount-a12', 'a12-50', 'a12-28')


def main():
    now = datetime.datetime.now(datetime.timezone.utc)
    run = json.loads((HERE/'local/continuation.json').read_text())
    start = datetime.datetime.fromisoformat(run['start_utc'].replace('Z', '+00:00'))
    rows = []
    for unit in UNITS:
        level = main_level(unit)
        for index in range(35):
            paths = list((HERE/'local/fits'/unit/f'{index:02d}').glob(f'L{level}_*.json'))
            docs = [(p, json.loads(p.read_text())) for p in paths]
            valid = [(p,d) for p,d in docs if d['quality']['passes']]
            if not valid:
                continue
            p, d = min(valid, key=lambda x:(x[1]['objective'], str(x[0])))
            regressions = [s for s,v in d['per_scene'].get('photo_iso200', {}).items()
                if v['candidate']['de00']['median']>v['current']['de00']['median']+1e-10
                or v['candidate']['de00']['p95']>v['current']['de00']['p95']+1e-10]
            row = dict(unit=unit, index=index, name=d['name'], fit=str(p.relative_to(HERE)),
                       record_sha256=d['record']['sha256'], origin=d['origin'],
                       backend=d.get('backend'), scene_regressions=regressions,
                       main_group='synthetic' if unit=='a12-28' else 'photo_iso200',
                       gain=d['gain_over_current_pp'], candidate_scores={g:v['candidate']['similarity_percent']
                           for g,v in d['scores'].items() if v})
            rows.append(row)
    counts = collections.Counter(r['unit'] for r in rows)
    lines = [f'本轮继续拟合，更新于 {now.isoformat()}，已用 {(now-start).total_seconds()/3600:.2f} 小时，时间盒 6 小时。', '',
        f'已收到 fit-fast-r1 精确路径切换通知，任务接入等价检查通过。采用冻结副本、exact 求解器、nice 15，每进程单线程数学库。当前最多 {run["max_compute_processes"]} 个计算进程，原3进程池按用户允许结束后已收紧计算锁。每个配方独立运行，单项上限 25 分钟，每批最多 9 项。', '',
        f'主档案已有保存记录 {len(rows)}/105：MOUNT {counts["mount-a12"]}/35，50mm {counts["a12-50"]}/35，28mm {counts["a12-28"]}/35。完整重放验收和最终 candidate_registry 尚待本轮汇总。', '',
        'MOUNT 03 的场景回退已从完整记录重新计算，普通 Standard 路径与保存预测逐像素一致。10 月 31 日 192 点的中位误差回退集中在黑白端，中间亮度和尾部误差改善；保留场景复核状态，不按该留出重选参数。详见 mount03_scene_review.json。', '',
        '以下均为电脑预测，表内分数对应按整数训练损失选出的已保存记录。']
    lines += ['', '| 单元及配方 | 训练相似度% | 合成相似度% | ISO200照片相似度% | 主要留出提升百分点 | 场景回退组数 |',
              '| --- | --- | --- | --- | --- | --- |']
    def f(v):
        return '—' if v is None else f'{v:.2f}'
    for r in rows:
        if r['unit']=='mount-a12' and r['index'] in (29,31,32):
            scores = r['candidate_scores']
            lines.append('| '+' | '.join([r['unit']+' '+r['name'],f(scores.get('train')),f(scores.get('synthetic')),
                f(scores.get('photo_iso200')),f(r['gain'].get(r['main_group'])),str(len(r['scene_regressions']))])+' |')
    lines += ['', 'MOUNT L1 已按部分可用的现场结论开放；三通道生效与命名有依据，定量幅度未闭合，不做全局RGB增益修正。L1将单列实测域与模型外推收益。1894–1900已由机主口头确认原厂04、无微调、日光预设；当前整组作新的标定外层留出。28mm仅报合成成绩。', '',
        '仍未构建 DAT，未访问卡或机主 Studio。派生数据只写 Git 忽略的 local/。本轮 Scratch 使用中，结束时清理；上轮封存文件保存在 local/checkpoint_before_continuation_*。']
    (HERE/'PROGRESS.md').write_text('\n'.join(lines)+'\n')
    folder = HERE/'local/progress_checkpoints'
    folder.mkdir(exist_ok=True)
    (folder/(now.strftime('%Y%m%dT%H%M%SZ')+'.json')).write_text(json.dumps(dict(created_utc=now.isoformat(),
        completed_main_profiles=len(rows), by_unit=dict(counts), profiles=rows), ensure_ascii=False, indent=2)+'\n')
    print('PROGRESS', len(rows), '/105', dict(counts), flush=True)


if __name__ == '__main__':
    main()
