"""Publish only linked, semantically accepted final model DATs to package roots."""
from pathlib import Path
import json
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import common as C
C.setup();C.compute_gate('publish-final-local-packages')
static=json.loads((C.LOCAL/'acceptance/model/static.json').read_text())
assert static['status']=='PASS'
proof=json.loads((C.LOCAL/'data-only-proof.json').read_text());assert proof['status']=='PASS'
published=[]
for profile,root in C.PACKAGES.items():
    artifact=C.artifact(profile,'model');raw=artifact['dat'].read_bytes();manifest=json.loads(artifact['manifest'].read_text())
    assert C.sha(raw)==manifest['dat_sha256'] and static['record_manifest_sha256'][profile]==C.sha(artifact['records'].read_bytes())
    assert manifest['main_request']<=manifest['main_limit'] and manifest['code_bytes']<=manifest['code_limit']
    audit=json.loads((C.LOCAL/'acceptance/model'/('byte-audit-'+profile+'.json')).read_text())
    assert audit['status']=='PASS' and audit['DAT_sha256']==manifest['dat_sha256'] and not audit['unexplained_bytes']
    for backend in ('c','python'):
        service=json.loads((C.LOCAL/'acceptance/model'/f'service-{profile}-{backend}.json').read_text())
        assert service['status']=='PASS' and service['DAT_sha256']==manifest['dat_sha256'] and len(service['rows'])==54
    sd=root/'local/SD_ROOT';sd.mkdir(parents=True,exist_ok=True)
    (sd/'GXRCE.DAT').write_bytes(raw);(root/'local/GXRCE.DAT').write_bytes(raw)
    manifest.update(status='LOCAL_HOST_ACCEPTED_RUNTIME_PENDING',dataset='model',lcd_screenshot='OPEN',resident_unchanged=True,body_unchanged=True)
    C.save(root/'MANIFEST',manifest)
    (root/'SHA256SUMS').write_text(manifest['dat_sha256']+'  local/SD_ROOT/GXRCE.DAT\n'+manifest['dat_sha256']+'  local/GXRCE.DAT\n')
    text=f'''# g157 {profile}

本地 DAT 包，机身 v3.10，resident 保持原样。DAT 在 [local/SD_ROOT/GXRCE.DAT](local/SD_ROOT/GXRCE.DAT)。

SHA-256：`{manifest['dat_sha256']}`。DAT {len(raw):,} B，实际主请求 {manifest['main_request']:,} / {manifest['main_limit']:,} B。

BOOT 自动套用{'打开' if profile=='test' else '关闭'}；读回和诊断打开。三单元官方 Acros 与 C040 记录按冻结清单接入。所有单元保留 18 Looks、八基础槽、三用户项和状态项，八物理行。

{'test 使用设计的容量备用数据：50mm HNCS HiCon、07、08 退回 g156 test 记录。' if profile=='test' else 'release 保留其余三条 50mm release 数据改进。'}

完整验收及 OPEN 以 [research/g157/REPORT.md](../../research/g157/REPORT.md) 为准。现有模拟器没有 LCD 像素输出，尚无诊断页 LCD 截图；本地包不代表真实相机、关机 NAND 或首拍验收。未接触相机或 SD 卡。

早期数据对照保存在 local/variants/control/，最终数据清单在 research/g157/local/model-records-{profile}.json。不要用对照文件覆盖最终包。
'''
    (root/'README.md').write_text(text)
    published.append(manifest)
C.save(C.LOCAL/'published.json',dict(status='PASS',packages=published))
print(json.dumps(dict(status='PASS',published=[r['dat_sha256'] for r in published])))
