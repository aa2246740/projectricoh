"""Create the two-file SD_ROOT and a deterministic local review archive."""
import json
from pathlib import Path
import sys
import zipfile
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import *


def main():
    guard(create_tmp=False)
    root=PACKAGE/'local/SD_ROOT'
    raw=(root/'GXRCE.DAT').read_bytes()
    receipt=json.loads((HERE/'evidence/build.json').read_text())
    assert sha(raw)==receipt['dat_sha256']
    readme='''GXR 三曲线响应探针 r1，复审通过后使用。

只替换卡根 GXRCE.DAT，机身保持当前 v3.9，不刷机身。
完整步骤：解压目录的 OWNER_STEPS.md
电脑色块页：解压目录的 patches.html
只有 SD_ROOT 内的 DAT 和本说明放在卡上，色块页留在电脑。

先完成既定的 28mm、50mm v3.9 升级与 looks18 试用，再开始本探针。
今晚只用 MOUNT：M26 A / M26 R+2 / M26 G+2 / M26 B+2。
拍 A、R×3、A、G×3、A、B×3、A，共13张。
每次切换后按 OK 退出；A拍一张，各扰动分开按三次快门。
50mm、28mm 条目保留供后续复核，本轮不加拍。
M 档、ISO200、日光白平衡，固定曝光与机位，保留原始 RAW+JPG。
总共 13 次快门。C120 未包含在本轮 DAT。

结束先选 04 Std 并按 OK，再关机。
恢复时把卡上的 G154L.DAT 复制成 GXRCE.DAT，不刷机身。
G154L.DAT 的 SHA-256：
5f6191c88e7691472541dce245df67679390aa850ffd110e8f8eb35f4b24c681
另一份备份 G154T.DAT：ac4263a0083aff1f04ab1433029b7ba354d67083ad09292f2af49bbc59abb83e
异常时停止本轮，关机后换回原 DAT；需要时拔电池 10 秒再冷启动。
'''
    (root/'README.txt').write_text(readme)
    assert {p.name for p in root.iterdir()}=={'GXRCE.DAT','README.txt'}
    files={f'SD_ROOT/{p.name}':p.read_bytes() for p in sorted(root.iterdir())}
    for name in ('OWNER_STEPS.md','patches.html'):
        data=(HERE/name).read_bytes()
        (PACKAGE/'local'/name).write_bytes(data)
        files[name]=data
    sums=''.join(f'{sha(data)}  {name}\n' for name,data in files.items())
    archive=PACKAGE/'local/GXR-probe-r1.zip'
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for name,data in {**files,'SHA256SUMS':sums.encode()}.items():
            info=zipfile.ZipInfo(name,date_time=(2026,11,2,0,0,0));info.external_attr=0o100644<<16
            info.compress_type=zipfile.ZIP_DEFLATED
            z.writestr(info,data,compress_type=zipfile.ZIP_DEFLATED,compresslevel=9)
    with zipfile.ZipFile(archive) as z:
        assert set(z.namelist())==set(files)|{'SHA256SUMS'}
        assert z.read('SD_ROOT/GXRCE.DAT')==raw
        assert z.read('SHA256SUMS').decode()==sums
    manifest=dict(variant='g154-type26-probe-r1',generation=154,body_sha256=BODY_SHA,
                  baseline_dat_sha256=BASE_SHA,dat_sha256=sha(raw),dat_bytes=len(raw),
                  archive_sha256=sha(archive.read_bytes()),archive_bytes=archive.stat().st_size,
                  sd_root_files=['GXRCE.DAT','README.txt'],source_C_unchanged=True,
                  physical_rows=8,logical_rows_per_unit=13,probes_per_unit=4,photo_count=13,
                  owner_unit='MOUNT',other_unit_photos_deferred=True,
                  c120_included=False,sizes=receipt['sizes'])
    save(PACKAGE/'MANIFEST.json',manifest)
    paths=[root/'GXRCE.DAT',root/'README.txt',PACKAGE/'local/OWNER_STEPS.md',
           PACKAGE/'local/patches.html',archive,PACKAGE/'MANIFEST.json']
    (PACKAGE/'SHA256SUMS').write_text(''.join(f'{sha(p.read_bytes())}  {p.relative_to(ROOT)}\n' for p in paths))
    save(HERE/'evidence/package.json',dict(status='PASS',**manifest,archive_round_trip=True))
    print(json.dumps(manifest))


if __name__=='__main__':main()
