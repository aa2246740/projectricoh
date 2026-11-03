"""Record the preflight stop and preserve evidence; never run acceptance or stage."""
import json
import os
from pathlib import Path
import plistlib
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as c


def main():
    info = plistlib.loads(subprocess.check_output(['/usr/sbin/diskutil', 'info', '-plist', '/Volumes/Workspace']))
    assert info['MountPoint'] == '/Volumes/Workspace' and info['FilesystemType'] == 'apfs'
    assert info['VolumeUUID'] == c.UUID and info['WritableVolume'] and info['WritableMedia']
    assert os.access('/Volumes/Workspace', os.W_OK)
    disk = subprocess.check_output(['/bin/df', '-h', '/Volumes/Workspace'], text=True)
    out = c.LOCAL / 'round2'
    failure = json.loads((out / 'failure.json').read_text())
    assert failure['status'] == 'FAILED_STOPPED' and not failure['card_files_staged']
    assert not (out / 'commands.jsonl').exists() and not (out / 'host').exists()
    assert not (c.LOCAL / 'card_update/GXRCE.DAT').exists()
    before = json.loads((c.LOCAL / 'inputs-before.json').read_text())
    after = c.snapshot()
    differences = [dict(path=p, before_sha256=before.get(p), current_sha256=after.get(p))
                   for p in sorted(before.keys() | after.keys()) if before.get(p) != after.get(p)]
    assert differences
    c.save(out / 'scope-after.json', dict(status='INPUT_DRIFT_STOPPED', protected_inputs=len(before),
           current_inputs=len(after), unchanged_inputs=sum(after.get(p) == h for p, h in before.items()),
           differences=differences, acceptance_run=False, card_files_staged=False))
    summary = dict(status='FAILED_STOPPED', failed_gate='round-1 protected-input snapshot equality',
                   differences=differences, host_compile_run=False, validator_rerun=False,
                   round2_host_cases=0, GXTS_host_tests='NOT_RUN',
                   card_files_staged=False, camera_acceptance=False,
                   candidate_sha256=c.sha(c.OUT / 'GXRCE.DAT'),
                   candidate_generation=106, candidate_bytes=(c.OUT / 'GXRCE.DAT').stat().st_size,
                   card_DAT_first='frozen approved resident behavior; original iv expectation withdrawn')
    c.save(out / 'verification.json', summary)
    c.write(out / 'volume-after.txt', disk.encode())
    raw_log = '''Traceback (most recent call last):
  File "/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/firmware/full_r4/verify_round2.py", line 158, in <module>
    main()
  File "/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/firmware/full_r4/verify_round2.py", line 100, in main
    assert c.snapshot() == inputs
AssertionError
'''
    c.write(out / 'logs/verify-round2-failure.log', raw_log.encode())
    rows = '\n'.join(f"- `{r['path']}`：第一轮 `{r['before_sha256']}`；当前 `{r['current_sha256']}`。" for r in differences)
    report = f'''# full-r4 第二轮报告

第二轮在冻结输入检查处停止，行为测试尚未运行，卡包保持 BLOCKED_NOT_STAGED。没有放宽检查。

已核实：第一轮 297 项 SHA256SUMS 全部通过，原有 298 个文件已冻结摘要。第一轮报告、清单和卡包 manifest 的副本在 [round1/](local/round2/round1/)，其余第一轮证据和失败日志保留原位。

481 个受保护输入中有 {len(differences)} 个与第一轮不同：

{rows}

本轮未写这些文件。完整差异见 [scope-after.json](local/round2/scope-after.json)，失败栈见 [verify-round2-failure.log](local/round2/logs/verify-round2-failure.log)。检查发生在编译和测试之前；(iv-a)、(iv-b)、三单元 GXTS 保存与冷启动、(d) 四槽更新均未运行，不能报告保留或重置结果。

full-r4 候选未变，generation 106，59,516 B，SHA-256：

```text
{summary['candidate_sha256']}
```

第一轮已核实的三条替换、48 槽展开和 effective-rows、仅 type-64 BSS 重定位低半部差异仍由原证据覆盖，见 [第一轮报告](local/round2/round1/REPORT.md)。本轮未修改容器、引擎、resident 或 body。

有效卡 DAT 优先加载、IROM 作为回退，是批准 resident 的冻结行为。卡 DAT=105 时要求会话加载 IROM=106 的原 (iv) 预期已撤回，不属于 full-r4 缺陷。实用规则是：任何卡上都不能留下较旧的 GXRCE.DAT。

全部验收通过后的卡侧流程为：关机，取卡，删除 GXRCE.OK，删除任何 GXRCE.DAT，只把新容器复制为 GXRCE.DAT，其它文件全部保留。本轮未暂存 GXRCE.DAT，未接触真实卡。

新增夹具为 [host_round2.c](host_round2.c) 和 [verify_round2.py](verify_round2.py)，尚未编译或验证。父任务需审阅上述输入变化并提供批准的冻结输入，再继续第二轮。原断言保留。

未知仍包括旧 DAT 冲突会话的实际主机结果、四槽 GXTS 更新结果，以及相机 UI、M32R 执行、实际 rename 和掉电持久化。输出仅在 firmware/full_r4/；未访问相机卡、刷机、启动子代理、安装包、commit 或 push。新增记录与第一轮证据由 [SHA256SUMS](SHA256SUMS) 覆盖。
'''
    (c.HERE / 'REPORT.md').write_text(report)
    frozen = json.loads((out / 'round1-files.json').read_text())
    preserved = []
    for rel, digest in frozen.items():
        p = out / 'round1' / rel if rel in ('REPORT.md', 'SHA256SUMS') else c.HERE / rel
        assert c.sha(p) == digest, rel
        preserved.append(dict(original=rel, retained=str(p.relative_to(c.HERE)), sha256=digest))
    c.save(out / 'round1-preservation.json', dict(status='PASS', files=len(preserved), preserved=preserved))
    assert c.sha(c.LOCAL / 'card_update/manifest.json') == frozen['local/card_update/manifest.json']
    checksum = c.HERE / 'SHA256SUMS'
    files = [p for p in sorted(c.HERE.rglob('*')) if p.is_file() and p != checksum]
    checksum.write_text(''.join(f'{c.sha(p)}  {p.relative_to(c.HERE).as_posix()}\n' for p in files))
    print(json.dumps(dict(status=summary['status'], differences=differences,
                          round1_files_preserved=len(preserved), checksum_files=len(files),
                          card_files_staged=False), ensure_ascii=False))


if __name__ == '__main__':
    main()
