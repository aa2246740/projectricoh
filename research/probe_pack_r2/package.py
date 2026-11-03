"""Package the final DAT and standalone owner materials, deterministically."""
from pathlib import Path
import json
import sys
import zipfile
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import *


def main():
    guard(create_tmp=False)
    root=PACKAGE/'local/SD_ROOT';raw=(root/'GXRCE.DAT').read_bytes()
    build=json.loads((HERE/'evidence/build.json').read_text());assert sha(raw)==build['dat_sha256']
    readme=f'''GXR 探针 2，复审通过后使用。

只适用于 v3.9，机身 ilaunch3 8233a1c4。刷 v3.10 后不能使用这个包。
只把 GXRCE.DAT 放到卡根覆盖。机身、resident 和单元固件不改，不刷机。
新 DAT SHA-256：{sha(raw)}

电脑打开 ramp2.html，完整步骤看 OWNER_STEPS_PROBE2.md。
MOUNT，35mm f/2 复刻版镜头，实际光圈 f/5.6。
MacBook 内建屏，摄影（P3-D65），固定亮度。
M 档、ISO200、日光白平衡、单张、RAW+JPG，固定 1/15。
P1 页：M26 A / P1 R-2 / P1 G-2 / P1 B-2 / M26 A，共 5 张。
P2 页：M26 A / P2 R+2 / P2 G+2 / P2 B+2 / P2 R+2 / P2 G+2 / P2 B+2 / M26 A，共 8 张。
P2 同时改零基节点 8 和 19。两页共 13 张，曝光不变，切页时相机不动。
每张选择完整条目名，按 OK 退出菜单，再按一次快门。

拍完选 04 Std，按 OK，再关机。
仍用 v3.9 时，把卡上的 G154L.DAT 复制成 GXRCE.DAT 即可恢复 looks18。
G154L.DAT SHA-256：{BASE_SHA}
安全推出卡，开机确认 04 Std。不刷机身。
v3.10 请用对应版本的数据包，不能用本探针或本恢复 DAT。

出错先停止，保留原始照片并记下位置。菜单能用时选 04 Std、OK、关机，再恢复 DAT。
菜单卡住时关机、取电池 10 秒，换回恢复 DAT 后再开机；仍异常就停止。
不要补中间一张。需要重拍时，从 P1 第一张 A 重拍整组。
'''
    (root/'README.txt').write_text(readme)
    assert {p.name for p in root.iterdir()}=={'GXRCE.DAT','README.txt'}
    files={f'SD_ROOT/{p.name}':p.read_bytes() for p in sorted(root.iterdir())}
    for name in ('OWNER_STEPS_PROBE2.md','ramp2.html'):
        data=(HERE/name).read_bytes();(PACKAGE/'local'/name).write_bytes(data);files[name]=data
    sums=''.join(sha(data)+'  '+name+'\n' for name,data in files.items())
    archive=PACKAGE/'local/GXR-probe2.zip'
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for name,data in {**files,'SHA256SUMS':sums.encode()}.items():
            info=zipfile.ZipInfo(name,date_time=(2026,11,3,0,0,0));info.external_attr=0o100644<<16
            z.writestr(info,data,compress_type=zipfile.ZIP_DEFLATED,compresslevel=9)
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None and len(z.namelist())==5
        assert z.read('SD_ROOT/GXRCE.DAT')==raw
        for line in z.read('SHA256SUMS').decode().splitlines():
            digest,name=line.split('  ',1);assert sha(z.read(name))==digest
    manifest=dict(variant='g154-probe2-v39-only',generation=154,body_sha256=BODY_SHA,baseline_dat_sha256=BASE_SHA,
        dat_sha256=sha(raw),dat_bytes=len(raw),archive_sha256=sha(archive.read_bytes()),archive_bytes=archive.stat().st_size,
        sd_root_files=['GXRCE.DAT','README.txt'],source_C_unchanged=True,physical_rows=8,
        visible_probes_per_unit=[4,4,7],logical_rows_per_unit=[13,13,16],P1_nodes=[16],P1_delta=-2,
        P2_nodes=[8,19],P2_delta=2,photo_count=13,exposure_s=1/15,actual_f_number=5.6,owner_unit='MOUNT',
        v39_only=True,v310_compatible=False,c120_included=False,sizes=build['sizes'])
    save(PACKAGE/'MANIFEST.json',manifest)
    paths=[root/'GXRCE.DAT',root/'README.txt',PACKAGE/'local/OWNER_STEPS_PROBE2.md',PACKAGE/'local/ramp2.html',archive,PACKAGE/'MANIFEST.json',PACKAGE/'README.md']
    (PACKAGE/'SHA256SUMS').write_text(''.join(sha(p.read_bytes())+'  '+str(p.relative_to(ROOT))+'\n' for p in paths))
    save(HERE/'evidence/package.json',dict(status='PASS',**manifest,archive_round_trip=True))
    print(json.dumps(dict(status='PASS',dat_sha256=sha(raw),archive_sha256=manifest['archive_sha256'],members=5)))


if __name__=='__main__':main()
