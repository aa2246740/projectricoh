#!/usr/bin/python3 -I
"""Collect strict-link results of every prototype variant into sizes.json.

Usage: collect.py <scratch variant root> <output sizes.json>
Each variant was linked by proto_strict.py (same directory) with
rv_resume_10=0x202b1210; build/strict.json is read as written.
"""
import json, sys
from pathlib import Path

DESC = {
    'base': 'v3.8 原样（门槛单处定义 176 B），应与已刷机身逐字节相同',
    'vH': '方案 r2 推荐 v3.9（H09 编辑表 + H10 按值换码），按方案差异重建',
    'vS1': '方案 r2 的 vH + H40/H41（带故障收尾），按方案差异重建',
    'c1': 'vS1 + C1：rv_check 去掉 rv_session 已重复的堆界和块头检查',
    'c2': 'vS1 + C2：rv_header 固定字节改为两段模板比较',
    'r1': 'vS1 + C1 + C2',
    'c4': 'r1 + C4：rv_hook_observe 不用跳转表',
    'c5': 'r1 + C5：rv_engine 不再把 6 个代次抄进请求，DAT 进入时自己读 root',
    'c6': 'r1 + C6：装载握手合并为一次调用，入口表仍在 READY 前逐项核对',
    'c7': 'r1 + C7：owned() 用基址加偏移读原生 UI 表（无效，0 B）',
    'c8': 'r1 + C8：7 个原生桩改为 4 B 索引桩加一张目标表',
    'r2': 'r1 + C4 + C5 + C6',
    'r3': 'r2 + C8 = 推荐的 vS1 腾挪版',
    'r3b': 'r3，但保留 RV_CHECK_HEAP 诊断码（C1 只去掉块头那一段）',
    'r4': 'r3 + K 保存扩到 K+0x190..0x19B（共 28 B）',
    'rN': '不改 DAT 接口的组合：r1 + C4 + C8（不含 C5/C6）',
    'neg80': 'r3 门槛设 80 B，应通过',
    'neg81': 'r3 门槛设 81 B，必须被链接拒绝',
    # review_body_reclaim 修改（r2fix.py 的开关）
    'f_cap': 'r3 + P1-01：CAP_BODY 进 READY 白名单和 RV_PRODUCT_CAPS',
    'f_args': 'r3 + P1-02：图像事件用 args[12]=原厂 SP、args[13]=r0 / 编码状态字',
    'f_done': 'r3 + P2-03：单次握手必须回 detail=RV_INIT_DONE',
    'f_frz': 'r3 + P1-03 选项 A：resident 冻结代次（原写法，撤回 C5）',
    'f_frzcp': 'r3 + P1-03 选项 A 紧凑写法（memcpy 前 4 个 + 2 次存）',
    'f_wide': 'r3 + P2-04：K 保存扩到 K+0x190..0x19B（即 r4 的改动）',
    'f_inl': 'r3 + 去掉 discard_main、ui_call 的 noinline',
    'r5b': 'r3 + cap + args + done（保留 C5，选项 B），不扩 K 保存',
    'r6a': 'r3 + cap + args + done + 冻结（紧凑）+ 扩 K 保存，未做内联',
    'r7': '推荐：r3 + cap + args + done + 冻结（紧凑）+ 扩 K 保存 + 内联',
    'r7b': 'r7 但保留 C5（选项 B）',
    'r7n': 'r7 但不扩 K 保存',
    'neg44': 'r7 门槛设 44 B，应通过',
    'neg45': 'r7 门槛设 45 B，必须被链接拒绝',
}
FRAMES = ('rv_hook_observe', 'rv_engine', 'rv_check', 'rv_session', 'rv_allocation',
          'rv_retire', 'rv_ui_abort', 'rv_code_guard', 'rv_invoke', 'rv_load', 'discard_main', 'body_ready', 'ui_call')


def main():
    root, out = Path(sys.argv[1]), Path(sys.argv[2])
    rows = []
    for v, d in DESC.items():
        j = json.loads((root / v / 'build/strict.json').read_text())
        row = dict(variant=v, what=d, strict_link_ok=j['link_ok'], code_bytes=j.get('code_bytes'),
                   code_end=j.get('code_end'), planning_margin=j['margin_definitions_in_ld'],
                   margin_defined_elsewhere=j['margin_definitions_elsewhere'])
        if j['link_ok']:
            row.update(free_above_24B_gate=j['free_above_24B_gate'], root=j['root'], root_pins=j['root_pins'],
                       root_vma=j['root_vma'], nonempty_sections_outside_allowed=j['nonempty_sections_outside_allowed'],
                       sha256=j['sha256'], stack_frames={k: j['stack_frames'][k] for k in FRAMES if k in j['stack_frames']})
        else:
            row.update(over_24B_gate=j.get('over_24B_gate'),
                       linker_message=[m.split(': ', 1)[-1] for m in j['link_messages']][:1])
        rows.append(row)
    out.write_text(json.dumps(rows, ensure_ascii=False, indent=1) + '\n')


if __name__ == '__main__':
    main()
