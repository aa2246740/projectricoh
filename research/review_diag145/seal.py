"""复核输入、清理本轮临时文件并生成可重读验证的 SHA256SUMS。"""
from pathlib import Path
import json
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import scope
scope.enable_fence()
out=scope.HERE
assert (out/'REVIEW.md').read_text().splitlines()[0]=='不能上卡'
expected=('static','rebuild','50mm-publish','mount-publish','28mm-refuse','28mm-retire-r2',
          'faults','cap-r2','native-failure','identity-probes','emulator-audit-r2','final-checks')
receipts={}
for label in expected:
    r=json.loads((out/(label+'-receipt.json')).read_text())
    assert r['returncode']==0,(label,r)
    assert r['timeout_seconds']==4200
    receipts[label]=dict(returncode=0,seconds=r['seconds'])
count=scope.freeze_check()
after=scope.inputs()
assert after==json.loads((out/'inputs-before.json').read_text())
scope.save(out/'inputs-after.json',after)

def remove_owned_tree(base):
    base=Path(base)
    if not base.exists():return
    assert not base.is_symlink()
    assert base==scope.SCRATCH or scope.SCRATCH in base.parents or out in base.parents
    for p in sorted(base.rglob('*'),key=lambda p:len(p.parts),reverse=True):
        assert not p.is_symlink(),str(p)
        if p.is_dir():p.rmdir()
        else:p.unlink()
    base.rmdir()

caches=[p for p in (out/'cases').glob('*/local/decode')]
caches.append(out/'probes/local/decode')
for p in caches:remove_owned_tree(p)
remove_owned_tree(scope.SCRATCH)
assert not scope.SCRATCH.exists()
scope.save(out/'tool-limitations.json',dict(
    rea=dict(code='capability_unavailable',category='unsupported_provider',
        message='This integration requires Linux and an absolute REA_BINWALK_COMMAND path to the caller-supplied tool',
        operation='inspect_firmware_regions',fallback='仓库已有 M32R objdump 和格式解析，不安装其他工具'),
    emulator='未重新执行原 36 分钟运行；只独立核对初态、保存结果和最终镜像',
    camera='未访问',card='未访问',subagents=0))
scope.save(out/'seal.json',dict(status='PASS',protected_inputs_unchanged=count,
    before_after_manifests_equal=True,tmpdir=str(scope.SCRATCH),tmpdir_removed=True,
    test_receipts=receipts,retained_initial_failures=['cap-receipt.json','emulator-audit-receipt.json'],
    final_dat_sha256=scope.sha(scope.ROOT/'firmware/package_v38_diag145/SD_ROOT/GXRCE.DAT'),
    review_sha256=scope.sha(out/'REVIEW.md'),
    manifest_policy='SHA256SUMS 包含本目录全部常规文件但不含自身；写入后逐条重新核对'))
files=sorted(p for p in out.rglob('*') if p.is_file() and p.name!='SHA256SUMS')
lines=[scope.sha(p)+'  '+str(p.relative_to(scope.ROOT)) for p in files]
(out/'SHA256SUMS').write_text('\n'.join(lines)+'\n')
for line in (out/'SHA256SUMS').read_text().splitlines():
    digest,name=line.split('  ',1)
    assert scope.sha(scope.ROOT/name)==digest,name
print('封存通过；输入不变',count,'个；输出校验通过',len(lines),'项；TMPDIR 已删除')
