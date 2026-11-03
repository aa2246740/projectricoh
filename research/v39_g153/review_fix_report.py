"""Write the final Chinese report only after the repair audit passes."""
from pathlib import Path
import datetime
import json
import shutil

HERE = Path(__file__).resolve().parent


def main():
    audit = json.loads((HERE / 'review_fix/evidence/audit.json').read_text())
    assert audit['status'] == 'PASS'
    release = audit['packages']['package_v39_g153']
    test = audit['packages']['package_v39_g153_test']
    reproduced = json.loads((HERE / 'review_fix/evidence/reproduce.json').read_text())
    assert reproduced['status'] == 'PASS'
    seconds = audit['test_wall_seconds']
    text = f'''可以交复审

g153 已合入正式交付的 g152 复审修复。原“待从 g152 移植”的 P1 已按下述四条跨退出合同和受影响回归验证，不再列为待合入项。两个 DAT 均已重新打包；机身沿用逐字节相同的 `8233a1c4…`。全程本机离线，未操作相机或存储卡，未联网、未写 Git、未开子代理。

## 移植 g152 复审修复

交付依据为 `research/looks_g152/REPORT.md`、840 项 `SHA256SUMS` 及 117 行 `review_fix/engine-change.diff`。840 项逐项核对通过；修复前 g153 的 4,545 项清单也全部通过。旧报告、清单和回执保存在 [review_fix/prior](review_fix/prior/REPORT.md)，旧源和二进制仍在 `local/initial-g153/`。没有把旧 DAT 的执行结果计为新 DAT 通过。

核心差异按严格上下文合入，无冲突。最终 `eng_core.c` 与交付修复版逐字节相同，SHA-256 为 `c62ca5337493c3ce974a30e8e7ca4b8bc68d593a0b965d1600dcc0fdeee7482d`。v3.9 的适配器与服务库不需改动。相对旧 g153，引擎源文件只有核心及效果空闲容量配置两项变化。

未建基线时，实际此前状态的资格限于本次 apply：开始时失效旧资格并重新捕获，结束及退出/重开/失归属/失效/重绑定边界再次撤销；T 和邻接观测一起失效。确认入口要求已有配方基线，实时校验不把未提交观测当配方台账。已有基线的 op 6、锁忙恢复及 v3.9 的 `op==2` 颗粒清零条件保留。

原复审脚本和 `after-refusal-*` 证据已复制到 `review_fix/legacy/`。执行时只把“首次拒绝后 `live_verified==1`”改为修复后的 0，其余原合同保留，并加严为实际此前状态的完整比较。50mm/MOUNT × 退出后实际 04/08，四项全部通过：本键服务顺序 `(6,0),(2,-2)`，S 零写，实际此前九行/T 和全部 4,096 B 的 S 在按键、退出和重开后保持。审计还直接比较每组保存的 505 B 单元状态和完整 S 文件，未用槽号代替字节证据。

## 最终两个包与空间

| 包 | 用户条目 | 效果 | DAT SHA-256 |
|---|---:|---:|---|
| [发布包](../../firmware/package_v39_g153/MANIFEST.json) | 0 | 10 | `{release['sha256']}` |
| [测试包](../../firmware/package_v39_g153_test/MANIFEST.json) | 3 | 10 | `{test['sha256']}` |

| 项 | 最终 B | 限制 B | 余量 B |
|---|---:|---:|---:|
| 主请求 | 107,072 | 107,612 | 540 |
| DAT 文件 | 90,164 | 97,792 | 7,628 |
| 代码 | 65,268 | 65,536 | 268 |
| BSS | 9,280 | 按链接结果计入主请求 | — |

主请求为 `7,628 + align4(90,164 + 9,280) = 107,072 B`。K=10，效果行池容量 8/28/32/32，实用 0/10/9/10，效果区 6,636 B。

修复使代码增加 216 B。保留旧 B=35 时实测主请求 107,304 B，只余 308 B，不满足原门槛，回执保存在 `review_fix/evidence/build-size-B35.json`。仅将空闲 B 行池 35 减至 28，省下 232 B，才得到当前余量。未放宽上限；10 个效果、24 个内置完整展开条目、7,904 B R3 和 1,984 B 用户扩展均与旧 g153 逐字节相同。无需缩减有效数据或其他功能。

## 机身身份核实

两包机身 SHA-256 均为 `{audit['body_sha256']}`。服务库、resident 的源码和构建产物，以及两包原机身文件，共 150 项逐项核对未变。本轮未重建 resident 或机身；打包直接复用已验证镜像。

正常重算源码身份仍得到 build id `785706aa2323d8f1c313e37c4eab94fdd2899c2f66d40e3dda9d505f32235f81` 和 ABI `dd55f5b9c81d35bd9f520b9449a6c463`，均与本轮 DAT 头一致。原 `identity_compare.py` 的完整字节门重新通过，相对 g151 只有身份和校验字共 34 B 改变。两个包各 28 个同伴文件重新逐字节核对官方 ZIP，SD_ROOT 各 30 个文件。

原机身的五步身份复核、两代交叉拒绝、三组各五亿步恢复、H09/H10/H40/H41 及颗粒回执保留，身份和机器码逐字节未变；它们属于上一轮执行证据，不计成本轮新 DAT 的复验。新 DAT 与该机身的成功装载由以下每个原生测试重新执行。

## 最终 DAT 的复验

| 组 | 本轮结果 |
|---|---|
| 跨退出快照 | 四项原复审 04/08 合同全部通过，逐字节比较 505 B 单元状态及完整 S。 |
| 锁忙缩减矩阵 | 48/48，通过 50mm/MOUNT × 四种切换 × held/race-at-s/transient × OK/半按。独立审计逐条复核 `[6]` 或 `[6,2]`，本键 BUSY 后不继续记录，S 零写，九行/T、完整 S 和 56 B 引用在退出/重开后不变。 |
| 未建基线回归 | 八项通过：两单元原 g150 非原厂首轮晚遇忙、两单元 T=0、九行变化、T 变化、无效捕获、补偿失败。错误支路为 ERR 并保持 uncertainty；实际此前状态的补偿不再依赖前一事务资格。 |
| 效果应用 | 三单元各十个效果，共 30 次，通过完整九行/T、552 B、完整 S、确认/重开及断电模型恢复。 |
| 状态与记录回归 | 50mm 冷启动、确认、启动 T、首次读回；MOUNT 确认、启动 T、发布/测试包双向记录；28mm 冷启动，共九项通过。错误页和失归属另两项通过。 |
| 同类事务 | 退出后实际状态为效果、多次拒绝后成功、原生半按后模型恢复实际行再重开，三项通过。半按夹具比较九行/T、完整 S、W 和资格；关闭期间恢复单元行是明确模型输入，没有执行真实拍摄。 |

全部 {audit['foreground_jobs']} 个前台作业通过。本轮所选测试的墙钟跨度 {seconds/60:.1f} 分钟，子作业累计 {audit['job_seconds']/60:.1f} 分钟；并行子作业用时不能直接当墙钟相加。实测最大并发 {audit['maximum_concurrent_jobs']}，nice 均为 10，每批均待两项退出后再换批。每进程独立 Scratch 目录，超时至少为相应历史耗时三倍。最终 DAT、脚本、日志及时间绑定保存在 `evidence/fix-*-receipt.json`、`review_fix/evidence/phase-*.json` 和 [最终审计](review_fix/evidence/audit.json)。

相机指令模型使用 `tools/native_harness` 的 Python 后端；机身原恢复和颗粒参照使用 `tools/gxr_emulator_batch`。没有使用尚在复审的 C 指令后端。原生 getter、编码器和部分系统行为仍是声明的主机模型。

完整 144 项锁忙、99 条旧回归全组合、数学全值域、全格式拒收、空/49 行及全部名字夹具、实机 LCD/RPC/RTOS/画质均留给发布复审，逐项依据见 [差量范围](review_fix/SCOPE.md)。服务库和机身未变，格式与有效数据也未变，本轮测试集中在快照有效期和空闲容量缩减的受影响路径。

## 复跑与封存

正式修复及输入清单绑定见 `evidence/p1-import.json`。移植重放后的 {reproduced['unchanged_source_files']} 个源码文件及重新构建的 DAT、ELF、机器码和布局均逐字节相同，见 `review_fix/evidence/reproduce.json`。没有重建机身。复跑入口如下，命令均在仓库根执行：

```sh
nice -n 10 sandbox-exec -f research/v39_g153/offline.sb \\
  /usr/bin/python3 -I -B research/v39_g153/build.py dat
nice -n 10 sandbox-exec -f research/v39_g153/offline.sb \\
  /usr/bin/python3 -I -B research/v39_g153/review_fix_package.py
nice -n 10 sandbox-exec -f research/v39_g153/offline.sb \\
  /usr/bin/python3 -I -B research/v39_g153/job.py --name rerun-after-refusal \\
  --timeout 3600 review_fix_checks.py after-refusal --unit mount --slot 8
```

批次入口为 `review_fix_run.py`，相应 phase 为 matrix、lifetime、snapshot、apply、regression、variants。phase 回执防止同名覆盖，独立重跑可以直接通过 `job.py` 取新名称；若使用批次入口，应先归档旧 phase 回执。移植重放仍可执行 `port.py`，它按正式导入回执固定核心摘要，不能自行跟随工作区上游文件变化。

准备阶段首次应用差异及旧移植入口重放时，系统临时路径不在允许写入范围内，因此被拒绝；为两个入口固定指定 Scratch 后均通过，原日志保留。B=35 的空间试建不满足门槛，测量完整保留。

哈希已更新到 [FLASH.md](FLASH.md)；原 `research/body_v39/FLASH.md` 处于只读范围，本轮继续使用获准目录内的 FLASH.md。两包和本目录各有 `SHA256SUMS`。测试退出和临时目录删除见 `review_fix/evidence/cleanup.json`；最终封存后逐项复核清单。
'''
    (HERE / 'REPORT.md').write_text(text)
    old_scope = HERE / 'review_fix/prior/SCOPE.md'
    if not old_scope.exists():
        shutil.copyfile(HERE / 'SCOPE.md', old_scope)
    (HERE / 'SCOPE.md').write_text(
        '# g153 当前复验范围\n\n'
        '正式 g152 复审修复的当前范围见 [review_fix/SCOPE.md](review_fix/SCOPE.md)，'
        '实际通过项以 [REPORT.md](REPORT.md) 和新 DAT 回执为准。\n\n'
        '修复前的范围保存在 [review_fix/prior/SCOPE.md](review_fix/prior/SCOPE.md)，'
        '不计作本轮新 DAT 的执行结果。\n')
    with (HERE / 'PROGRESS.md').open('a') as output:
        output.write(datetime.datetime.now(datetime.timezone.utc).isoformat() +
                     '：正式修复、两包、跨退出四项、48 项矩阵与受影响回归全部通过；'
                     '报告结论更新为可以交复审。\n')


if __name__ == '__main__':
    main()
