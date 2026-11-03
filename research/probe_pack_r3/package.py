"""Package the final DAT and single eight-shot owner page deterministically."""
from pathlib import Path
import json
import sys
import zipfile
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import *


def main():
    guard(create_tmp=False);root=PACKAGE/'local/SD_ROOT';raw=(root/'GXRCE.DAT').read_bytes()
    build=json.loads((HERE/'evidence/build.json').read_text());assert sha(raw)==build['dat_sha256']
    readme=f'''GXR 探针 3，复审通过后使用。

仅用于 v3.9 / g154，机身 ilaunch3 8233a1c4。刷 v3.10 后不能用这个包。
卡操作由协助者负责，只换卡根 GXRCE.DAT，不改或刷机身、resident、单元固件。
新 DAT SHA-256：{sha(raw)}

电脑离线打开 ramp3.html，完整短步骤看 OWNER_STEPS_PROBE3.md。
只拍一组 8 张：A、R+2、R-2、G+2、G-2、B+2、B-2、A。均为零基节点 16。
实际条目名为 M26 A、P1 R+2、P1 R-2、P1 G+2、P1 G-2、P1 B+2、P1 B-2。
先滚动核对七种名字。按 OK 退出菜单，再拍一张 RAW+JPG。
页面可按 →/空格前进、← 返回；也可以不按键、照步骤拍。
漏按页码不用补拍。后续按照片响应识别，标签与响应冲突会分别记录。
完整外框、四角标、底部三色块必须入镜，四周留空。
MOUNT，35mm f/2 复刻版手动镜头，光圈 f/5.6。
MacBook 内建屏、摄影（P3-D65），固定亮度，关灯拉窗帘。
M 档、1/15、ISO 200、日光白平衡、单张，之后不改设置或构图。

拍完选 04 Std、OK、关机，卡交协助者恢复。
仍用 v3.9 时，协助者把 G154L.DAT 复制成 GXRCE.DAT，安全推出卡。
G154L.DAT SHA-256：{BASE_SHA}
机主不用复制文件或核对哈希。v3.10 要用对应数据包，本探针和本恢复 DAT 都不能用。

名字不全、外框裁切、拍错或报错就停止，保留全部照片，不补中间一张。
能操作时选 04 Std、OK、关机；卡住时关机、取出电池，交协助者恢复后再处理。
'''
    (root/'README.txt').write_text(readme)
    assert {p.name for p in root.iterdir()}=={'GXRCE.DAT','README.txt'}
    files={f'SD_ROOT/{p.name}':p.read_bytes() for p in sorted(root.iterdir())}
    for name in ('OWNER_STEPS_PROBE3.md','ramp3.html'):
        data=(HERE/name).read_bytes();(PACKAGE/'local'/name).write_bytes(data);files[name]=data
    sums=''.join(sha(data)+'  '+name+'\n' for name,data in files.items())
    archive=PACKAGE/'local/GXR-probe3.zip'
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for name,data in {**files,'SHA256SUMS':sums.encode()}.items():
            info=zipfile.ZipInfo(name,date_time=(2026,11,3,0,0,0));info.external_attr=0o100644<<16
            z.writestr(info,data,compress_type=zipfile.ZIP_DEFLATED,compresslevel=9)
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None and len(z.namelist())==5
        for line in z.read('SHA256SUMS').decode().splitlines():
            digest,name=line.split('  ',1);assert sha(z.read(name))==digest
    manifest=dict(variant='g154-probe3-v39-only',generation=154,body_sha256=BODY_SHA,baseline_dat_sha256=BASE_SHA,
        probe2_dat_sha256='102388ab2651d5cd308de2539f500c2718daedb6dd558a129f17dd41a8f382a9',
        dat_sha256=sha(raw),dat_bytes=len(raw),archive_sha256=sha(archive.read_bytes()),archive_bytes=archive.stat().st_size,
        sd_root_files=['GXRCE.DAT','README.txt'],source_C_unchanged=True,physical_rows=8,
        visible_probes_per_unit=[4,4,7],logical_rows_per_unit=[13,13,16],node=16,negative_delta=-2,positive_delta=2,
        photo_count=8,optional_set=False,exposure_s=1/15,actual_f_number=5.6,owner_unit='MOUNT',
        step_label_optional=True,response_identity_independent=True,v39_only=True,v310_compatible=False,
        c120_included=False,sizes=build['sizes'])
    save(PACKAGE/'MANIFEST.json',manifest)
    paths=[root/'GXRCE.DAT',root/'README.txt',PACKAGE/'local/OWNER_STEPS_PROBE3.md',PACKAGE/'local/ramp3.html',
        archive,PACKAGE/'MANIFEST.json',PACKAGE/'README.md']
    (PACKAGE/'SHA256SUMS').write_text(''.join(sha(p.read_bytes())+'  '+str(p.relative_to(ROOT))+'\n' for p in paths))
    save(HERE/'evidence/package.json',dict(status='PASS',**manifest,archive_round_trip=True))
    print(json.dumps(dict(status='PASS',dat_sha256=sha(raw),archive_sha256=manifest['archive_sha256'],members=5)))


if __name__=='__main__':main()
