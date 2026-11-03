# -*- coding: utf-8 -*-
"""Render this round's report from completed, successful evidence only."""
from pathlib import Path
import hashlib,json,struct
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];OUT=HERE/'local';PACKAGE=ROOT/'firmware/package_v35_g117'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 dat=HERE/'candidate/local/full-r13/GXRCE.DAT';raw=dat.read_bytes();manifest=json.loads((HERE/'candidate/local/full-r13/manifest.json').read_text());static=json.loads((OUT/'static/summary.json').read_text())
 stages=json.loads((OUT/'host-stages.json').read_text());assert len(stages)==26 and all(r['returncode']==0 for r in stages)
 native=json.loads((OUT/'native-runs.json').read_text());assert len(native)==2 and all(r['returncode']==0 for r in native)
 baseline=json.loads((HERE/'native_harness/local/scenarios.json').read_text());assert len(baseline)==20 and all(not r['violations'] and not r['error'] for r in baseline)
 protected=json.loads((OUT/'protected-after.json').read_text());assert not protected['changed']
 runs=[json.loads(r) for r in (HERE/'candidate/local/v34c-host/runs.jsonl').read_text().splitlines()];assert len(runs)==258
 nstdout=(OUT/'native-v35-g117.stdout').read_text();assert 'PASS v35 scenarios 7' in nstdout and 'file_mutations=0' in nstdout
 assert dat.read_bytes()==(PACKAGE/'SD_ROOT/GXRCE.DAT').read_bytes()
 table=[
 ('basic 的黑盒计数','apply 后 log_writes > 0','log_writes = 0；T 读取和配方九行断言保留。'),
 ('first 冷启动矩阵','GXLS 记住的槽，缺省 01','始终 04；9 种旧记录 × 256 种设置模式均运行。'),
 ('first 未提交时 Fn2/OK','应用旧高亮槽','应用 04；未提交重开仍高亮 04。'),
 ('CTL 的无 SD 身份场景','应用后写 GXLS','应用仍成功，internal_mutations = 0。'),
 ('irom 的安装状态','RV_OK，至少一份新正式 DAT','RV_UNAVAILABLE；只保留原先存在的副本，零写、零 rename。'),
 ('blackbox 的 Fn2 和关闭','生成两个 4096 B SD 日志','两个 SD 日志均不生成；RAM 环和首次 seed 保留，flush = 0。'),
 ('blackbox 的本地证据导出','从模拟 SD 日志导出','从 RAM 导出 RAM_ONLY 文件；这不是卡上日志。'),
 ('legacy 的 GXTS','升级或保存成当前绑定、generation 1','所有旧副本逐字节不变，不读取旧微调，OK 只保留 RAM。'),
 ('store-fault 注入命中','create/write/close/rename 故障命中','这些存储路径不执行，fault_used = 0。'),
 ('store-fault 的 Fn2 值','存储失败后回滚默认 0','OK 在 RAM 接受 +2；原生 apply 失败检查保留在 rpc-faults 和 publish-failure。'),
 ('service-quarantine 初始 create','RV_OK，并取得写 token','RV_CAPABILITY，不生成写 token。'),
 ('service-quarantine 最后 write','已有写 token 被 quarantine 拒绝','已关闭的只读 token 返回 RV_STALE；DAT 读错误和三个 quarantine 拦截断言保留。'),
 ('log-fault','第二次日志写故障命中，第一份不变','完全不访问日志；注入不命中，两份预置旧日志均不变，会话仍可用。'),
 ('accepted-f02 的隐藏较新 IROM','安装探测命中 open=-1 后覆盖成当前代','不扫描安装源，hidden_hits = 0；较新副本保持原字节和 generation。'),
 ('conflict / same-conflict','安装返回 RV_CONFLICT 并置 quarantine','无安装，RV_UNAVAILABLE，不置安装 quarantine；所有真实 loader 拒绝和粘滞 quarantine 用例保留。'),
 ('daily 的 DAT→OK','DAT 消失，OK 出现','DAT 保留，OK 不生成。'),
 ('daily 的冷启动光标','首次 01，之后 08','两次都为 04，native cursor = 3。'),
 ('daily 的重启 Fn2 值','从 GXTS 读回 +3','配方默认 0。'),
 ('daily 的 OK 文件输出','内部写次数增加，GXTS 和 GXLS A/B 出现','内部写次数不变，三类文件均不创建；当次 RAM 值仍为 +3。'),
 ('history 的三类重启光标','旧 GXLS 槽、缺省 01 或上次提交槽','统一 04；192 对未关闭操作、24 个 ROM 重建槽、4096 B 设置区和换单元检查保留。'),
 ('全部阶段的 native 边界','无统一的五类尝试次数断言','新增 create/write/rename/delete/write-open = 0；失败的 open 也计数，无卡 32 次 H01 的 open 尝试不增加。'),
 ('原生 v3.5 场景的文件替身','从已安装 IROM DAT 提供程序','从卡 DAT 提供 117；禁止写调用和非零 open flags，三单元检查实际 cursor=4 和按键应用 01。'),
 ]
 calls=json.loads((OUT/'static/native-file-calls.json').read_text())
 why={0x6c14:'mark 的读回 helper；op=9 写能力门禁后，当前不可达。',0x6d64:'SD 失联收尾，仅关闭只读 token。',0x6d7c:'SD 失联收尾，仅关闭只读 token。',0x8b24:'普通文件 close，仅能取得只读 token。',0x8c2c:'不可达；op=5 要求 mode=write，只有被封死的 op=3 能生成该 token。',0x8c6c:'普通文件只读 transfer。',0x8f60:'普通 open，flags=0。',0x8fe4:'不可达；op=3 检查 CAP_FILE_WRITE，当前该位为 0。',0x91a0:'mark 读卡 DAT，flags=0；op=9 门禁后不可达。',0x91ac:'mark 读 IROM DAT，flags=0；op=9 门禁后不可达。',0x91c8:'mark 的只读 close；op=9 门禁后不可达。',0x91dc:'mark 的只读 close；op=9 门禁后不可达。',0x9210:'不可达；DAT→OK 的 op=9 入口有写能力门禁。',0x9270:'mark 读 EOF；op=9 门禁后不可达。',0x9284:'mark 读 EOF；op=9 门禁后不可达。',0x9374:'不可达；op=8 有写能力门禁。',0xa9c8:'不可达；op=7 有写能力门禁。',0xad74:'CTL open，flags=0。',0xad98:'CTL 只读。',0xadb8:'CTL 读 EOF。',0xadc4:'CTL 的只读 close。'}
 calltable='\n'.join('| `'+r['pc']+'` | '+r['service']+' | '+why[int(r['container_offset'],16)]+' |' for r in calls)
 exp='\n'.join('| '+a+' | '+b+' | '+c+' |' for a,b,c in table)
 stage_excerpt='\n'.join(r['stdout'].strip() for r in stages[:22])
 extra=stages[23]['stdout'].splitlines();extra_excerpt='\n'.join(extra[:-1])
 text=f'''# gen 117 只读容器交付记录

本轮容器构建、静态检查、22 个 Host 阶段及原生 harness 均 PASS。没有访问相机或卡，没有刷机。机身沿用指定 v3.5 映像；机身的另一路审查不在本报告的验收范围内，真机开机、LCD、拍摄和物理文件系统本轮未测。

## 交付物与绑定

SD_ROOT 恰好 30 个文件：指定 v3.5 ilaunch3、28 个官方文件和 gen 117 GXRCE.DAT。28 个官方文件与 genuine gxr-151.zip 逐字节相等，也与 artifacts/firmware/gxr-1.51/ 的对应文件相等。没有使用 04168d00… 的 mutant fixture。

| 项目 | 本轮结果 |
| --- | --- |
| GXRCE.DAT generation | 117 |
| GXRCE.DAT SHA-256 | `{sha(dat)}` |
| 文件 / engine / BSS | {len(raw):,} / {static['engine_bytes']:,} / {static['bss_bytes']:,} B |
| file+BSS | {static['file_bss_bytes']:,} B，低于 114,688 B 上限 |
| 文件上限 | 已恢复 65,536 B，余 {65536-len(raw):,} B，不需要 73,728 B 打包预算 |
| engine 上限 | 65,536 B，余 {65536-static['engine_bytes']:,} B |
| gen 116 对照 | 文件和 engine 各减 10,988 B，BSS 减 1,872 B |
| ilaunch3 SHA-256 | `6e9ea05868b2bb56fb60de0e8506aad7b952715c061009b2acc891b45d220b20` |
| ilaunch3 大小 | {(PACKAGE/'SD_ROOT/ilaunch3').stat().st_size:,} B |
| genuine ZIP SHA-256 | `3705984b8433c40d2ed4fd2600c11f03ed8a6de7dbe7f66efd38ee5ca15fc898` |
| resident build id | `{manifest['resident_build_id']}` |
| resident ABI | `{manifest['resident_abi_id']}` |

resident build id 和 ABI 已从 resident_v35 源码及工具链重新计算，均匹配。header 的 body trust 仍指向官方 ilaunch3，不把它与修改后机身的 SHA 混用。实际 DAT 的代码段与 engine.elf 相等；按重定位表移到 0x21004000 后，与 translated.elf 逐字节相等。

## 相对 gen 116 的改动

- ig_bx_flush 在入口返回 0，不读写任何文件；RAM 环、native seed、unit 和 apply 记录结构保留。
- ig_init 的首次和再次初始化都只返回 CAP_UI、CAP_S、CAP_W，撤掉 CAP_FILE_WRITE。
- install 在入口返回 RV_UNAVAILABLE，省去安装缓冲和文件扫描。remember_save 不执行，remember_load 拒绝旧记录，开机不读 GXLS 或 GXTS。
- preload_gxts 只从容器 metadata 取默认值。Fn2 的 OK 应用草稿后更新 RAM，不调用文件保存，也不进入 SaveFail 或存储失败回滚分支。
- eng_menu_open 在本次启动尚未提交配方时把光标放到 04；提交后放到当前已提交的槽。
- 打包器的文件上限恢复 65,536 B。保留原只读解析器及服务对旧文件的读取容量；没有启用 73,728 B 安装缓冲。

48 个 entry552、48 条 recipe records、三份 map、48 份 metadata 和三个 pin 与实际 gen 115、116 均相等，三单元 owner 都为 8。B5 每次写前重读邻字节的代码没有变化。成功 Fn2 的 RAM sticky apply 记录缺口 P2-01 沿用 gen 116，本轮没有改动它。48 组 metadata 默认值也已与旧的六参数默认值路径核对，未用参数的默认值均为 0。

## 最终机器码的无写入证明

两处 ig_init 的机器码在 0x2100B3A4、0x2100BB6C 装入 0x000E0000，再写入 reply.capabilities。CAP_FILE_WRITE 是 0x00010000，因此 resident 发布后的 session 不可能从该返回值取得写能力。resident loader 的初始化值 RV_READ_CAPS=0x7FFF 同样不含该位。

服务内 create 必须通过 CAP_FILE_WRITE 门禁；write 必须持有 create 才能生成的 write-mode token。rename、delete 和 DAT→OK mark 的入口都先检查该能力。以下列出最终 relocated engine 的全部 21 个原生文件调用点，包含 6 个 read。保留下来的写服务机器码均不可达。黑盒的文件调用已被编译器删除。

| relocated PC | 服务 | 本轮可达性与参数 |
| --- | --- | --- |
{calltable}

完整反汇编、每处调用前后的指令、native bridge 的原生地址和能力位检查见 [静态证据](../engine_v38_ro/local/static/)。所有可达 open 的 flags 都为 0，没有写模式 open。native create/write/rename/delete 的原生入口地址只由 bridge 装入，没有另一条硬编码绕行。

官方 close 的入口 0x200A437C 只在描述符模式为 1 时考虑回写；read 在 0x200A44D0 把模式设为 2。没有 write 时，不会经过 0x200A43F4 的缓冲回写，也不会走 P1-01 的 0x200A4400..4418 早退。29 个官方机器码用例实际执行，其中 16 个覆盖只读 open/read/close 的读失败和底层 close 失败组合，wrapper_count 始终回到 0；原先两次脏 close 失败耗尽计数的正对照也成功复现。底层 lookup、media 和 close 是显式替身，这不是物理卡试验。

resident_v35 的 loader.c、shared.c、resident.c 没有自行调用 create/write/rename/delete。loader.c 的 open 在第 22、90、91、92 行，均为 flags=0；read 在第 28 行，close 在第 34、94 行。没有修改 resident。

## 实际测试结果

22 个阶段与审查使用同一入口，ASan 和 UBSan 开启，-fno-sanitize-recover=all。共有 255 次原阶段 Host 场景、3 次 history 和 3 次新增 gen117 三单元场景。vectors 单独验证当前及历史数据。以下为实际输出：

```text
{stage_excerpt}
PASS historical power projections: three units, 192 unclosed pairs, 24 ROM-reset slots
```

新增用例在 jlaunch 50mm、qlaunch 28mm、l08firm MOUNT 上全部通过。每组都核对原生 create、write、rename、delete 的尝试次数与写模式 open 次数为 0，旧 GXLS/GXTS 的 open 次数也为 0。无卡用例移除 DAT、撤掉 SD 身份后模拟冷启动，旧 115 IROM 仍存在。连失败的 open 尝试也计数，32 次 H01 不增加尝试。

```text
{extra_excerpt}
```

原生 harness 会在自身目录写 decoder cache 和结果，因此按写入边界复制到 engine_v38_ro/native_harness 再执行。conformance.py、scenarios.py 与 tools 原文件字节相等，解释器未改；只改 ROOT 路由，并在 product_execute 的 open 日志里记录 flags。20 组既有场景运行旧 113、114、115 对照，violation 和 error 均为 0，不能单独算 gen117 验收。gen117 另用复制的 run_v35 场景绑定指定机身、卡 DAT 和本轮 ELF，执行实际 resident 与 engine 指令；文件系统、镜头 RPC 和调度仍有替身。

实际命令为：

```sh
/usr/bin/python3 -I -B firmware/engine_v38_ro/native_harness/conformance.py
/usr/bin/python3 -I -B firmware/engine_v38_ro/native_harness/scenarios.py
/usr/bin/python3 -I -B firmware/engine_v38_ro/run_v35_g117.py
```

实际输出为：

```text
{(OUT/'conformance.stdout').read_text().strip()}
{(OUT/'native-scenarios.stdout').read_text().strip().splitlines()[-1]}
{nstdout.strip()}
```

完整 stdout、stderr、命令、退出码和逐案例记录见 [本轮日志](../engine_v38_ro/local/host-stages.stdout)、[Host 结果](../engine_v38_ro/local/host-stages.json)、[原生结果](../engine_v38_ro/local/native-runs.json)、[官方 close 重放](../engine_v38_ro/native/replay-results.json)。没有把 Host 替身结果当作相机结果。

## 改动过的测试预期

只改变与停写、启动高亮和旧偏好有关的预期。CTL、配方字节、T、ISO、B5、RPC 故障后停止、发布失败、单元身份和完整设置区的检查均保留。逐条原始替换和完整差分见 [预期清单](../engine_v38_ro/local/host-expectation-changes.json) 和 [Host 差分](../engine_v38_ro/local/host117.patch)。表中的最后两项是新增检查及原生文件源的适配。

| 阶段或检查 | gen 116 预期 | gen 117 预期与原因 |
| --- | --- | --- |
{exp}

## 用户会看到什么

每次开机不自动恢复上次配方，纯 04 状态下列表高亮 04。显式应用 01 后重开列表高亮 01；应用 08 后关机，再开机仍是纯 04 并高亮 04。

Fn2 面板仍显示 Cont、Satu、HiLt、Shad 和 -5 到 +5 的数值。按 OK 后应用草稿并关闭面板，本次开机重开可看到刚才的值。它不显示 Saved，也不显示 SaveFail；关机后这些微调丢失，下次应用配方使用默认值。

gen117 不向卡上落黑盒，不安装到内部存储，也不把 GXRCE.DAT 改成 GXRCE.OK。卡必须留在相机中，每次开机都需要卡上的 GXRCE.DAT。格式化卡会删除配方容器。已有的旧 IROM DAT、GXLS、GXTS 和旧卡日志不被修改或清理；实际 115 IROM 副本不能替代本轮 117。

恢复使用卡 A 的 Stage2l-50mm。先挂 50mm，再按“+ 与回放”进入恢复更新；机身刷写必须挂着 50mm。本轮没有执行恢复或刷写。

## 重建与文件边界

默认构建绑定本报告所列 resident 身份。单独审查产生新 trust JSON 后，可机械重绑：

```sh
/usr/bin/python3 -I -B firmware/engine_v38_ro/candidate/build117.py --resident-trust <已审查的-trust.json>
```

本轮用当前 trust JSON 实际重建，DAT 的 SHA 和大小仍相同。重绑到不同身份会改变 DAT 的 SHA，需要按新机身重新核对。

本轮写入只在 firmware/engine_v38_ro 和 firmware/package_v35_g117。{protected['files']:,} 个冻结保护文件内容变化为 0。SD_ROOT 的 30 文件已逐项读回，SHA256SUMS 使用交付目录相对路径，包含报告和 30 个 SD 文件，不包含清单自身。
'''
 (PACKAGE/'REPORT.md').write_text(text)
 print('PASS generated current-round REPORT.md',len(text.splitlines()),'lines')
if __name__=='__main__':main()
