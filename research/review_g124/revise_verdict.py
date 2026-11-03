"""Carry the verified first-publication finding into the report and its generator."""
from pathlib import Path
OUT=Path(__file__).resolve().parent
source=OUT/'write_review.py';text=source.read_text()
old="    compiled=passed('evidence/compiled-review.json');assert compiled['status']=='PASS_SCOPED_WITH_P2'"
new="    compiled=read('evidence/compiled-review.json');assert compiled['status']=='FAIL_NATIVE_PUBLICATION'\n    assert read('evidence/cold-publication-verified.json')['status']=='P1_REPRODUCED'\n    p1=(OUT/'P1-first-publication.md').read_text()"
assert text.count(old)==1;text=text.replace(old,new)
changes=[
 ("    report=f'''可以上测试卡","    report=f'''不可以上测试卡"),
 ('gen 123 的一行 ERR 重入误写在最终 gen 124 DAT 上未再出现。','首次发布前的七行窗口仍可让重入方向键写原生 Image mode，随后八行界面指向 04，却保留 mode=5。这项继承 P1 阻断本轮放行。gen 123 的一行 ERR 问题在已发布八行视图上未再出现，不能替代首次发布过渡检查。'),
 ('未发现。本结论限于源码、最终打包字节','{p1}'),
 ('八行纪律针对仍归属 DAT 的已发布视图。','已发布视图的八行纪律通过；首次发布过渡不通过，见 P1-01。OK 和 ADJ 退出时，固定 resident 在 DAT 调用结束后、IRQ 关闭期间恢复原生七行，并清空 `ui_restore[0]`。七种视图的 21 个退出案例均未经过 Image setter。半按关闭叠层时可暂留隐藏的八行描述，等待后续原生构造。未核对的 H01 回退原生七项，没有显示为已应用配方。这些原生接管状态没有被计作八行 DAT 视图通过。'),
 ('冷启动模型没有自动应用用户记录，','无首次发布重入的冷启动模型没有自动应用用户记录，九行、T、Image mode 为 04。P1-01 证明一旦首次发布前被重入，Image mode 可变为 5，不能保证完整配方或纯 04。该 harness 的上电 WB 是合成输入，没有由原生完整开机建立，也没有所有上电设置、EEPROM 或实体断电后的全状态证明。永久通信失败时仍可能留有部分 W，系统显示 ERR 并锁定，不把该状态记为完整配方成功；这一故障边界继承 gen 121。'),
 ('| 原生界面写入 | 八行入口','| 原生界面写入 | 未闭合。已发布八行的 210 例及事务方向键重入通过，首次发布前仍有 P1-01 的 Image setter 写入。末端绘制另保留 P2-01。 |'),
 ('| 循环与内存 | 八行文字','| 循环与内存 | 八行文字、11 个参数、24 配置、最多 32 用户均有固定界限；导航最多 16 轮，补偿仍为 4+2；重编栈记录全部为静态帧，无 VLA。 |'),
 ('未发现已证实的新设置误写或退出回退。','P1-01 的首次发布错误在 gen 121 同样存在，未将它标成 gen 124 新增回退，但它仍阻断本轮明确的状态约束。三单元映射和 48 个打包槽位与 gen 121、gen 123 相同。gen 121 的十一行数值面板在 inflight 重入时没有八行保护，gen 124 改为八行。gen 122 的部分复位漏检、未核对八行配方仍能退出，以及 gen 123 当次一行 ERR 误写均未在本轮对应旧反例中重现。'),
]
lines=text.splitlines()
for prefix,replacement in changes:
    hits=[i for i,line in enumerate(lines) if line.startswith(prefix)];assert len(hits)==1,(prefix,hits)
    lines[hits[0]]=replacement
source.write_text('\n'.join(lines)+'\n')
report=OUT/'REVIEW.md';text=report.read_text();lines=text.splitlines();lines[0]='不可以上测试卡'
lines[2]=changes[1][1];text='\n'.join(lines)+'\n'
start=text.index('## P1\n\n')+len('## P1\n\n');end=text.index('## P2\n',start)
text=text[:start]+(OUT/'P1-first-publication.md').read_text()+'\n'+text[end:]
report.write_text(text)
print('Updated verdict to no-go; first-publication P1 included')
