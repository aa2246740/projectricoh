"""复用已有验收断言，输入绑定最终卡包，输出重定向至复审目录。"""
from pathlib import Path
import json
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import scope
scope.enable_fence()
unit, mode = sys.argv[1:3]
source = scope.ROOT / 'research/unit28_stock'
accept = scope.load(source / 'accept_diag145.py', 'review145_accept')
case = scope.HERE / 'cases' / (unit + '-' + mode)
case.mkdir(parents=True, exist_ok=True)
accept.HERE = accept.base.HERE = case
accept.DAT = scope.ROOT / 'firmware/package_v38_diag145/SD_ROOT/GXRCE.DAT'
accept.base.DAT = accept.DAT
accept.save = scope.save
original_boot = accept.boot
products = []
def observed_boot(*args, **kwargs):
    result = original_boot(*args, **kwargs)
    products.append(result[2])
    return result
accept.boot = observed_boot
sys.argv = [str(source / 'accept_diag145.py'), unit, mode]
accept.main()
for p in products:
    if accept.TRACE in p.files.paths:
        (case / 'trace.bin').write_bytes(bytes(p.files.paths[accept.TRACE]))
scope.save(case / 'identity.json', dict(dat_sha256=scope.sha(accept.DAT), inputs_unchanged=scope.freeze_check()))
print('最终卡包验收结束', unit, mode)
