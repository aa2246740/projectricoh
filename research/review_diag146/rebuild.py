"""原构建函数的隔离复跑，仅重定向输出、日志和临时目录。"""
from pathlib import Path
import copy
import json
import struct
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import scope
scope.enable_fence()
tree = scope.ROOT / 'firmware/engine_diag_v38_g146'
sys.path.insert(0, str(tree / 'candidate'))
sys.path.insert(0, str(scope.ROOT / 'research/unit28_stock'))
import common as c
import service_build

out = scope.HERE / 'rebuild'
out.mkdir(exist_ok=True)
c.LOCAL = out
c.SCRATCH = scope.SCRATCH
c.guard = lambda: scope.freeze_check()
c.save = scope.save
original_run = c.run

def run(args, label, **kwargs):
    args = [out / 'resident/engine-services/libgxr_services.a'
            if str(a) == str(tree / 'candidate/local/resident/engine-services/libgxr_services.a') else a for a in args]
    kwargs['timeout'] = 4200
    return original_run(args, label, **kwargs)

c.run = run
# 原脚本把元数据中的产物路径限定为 candidate 的相对路径；隔离复跑改用仓库相对路径。
service_source = (tree / 'candidate/service_build.py').read_text()
assert service_source.count('.relative_to(c.HERE)') == 2
exec(compile(service_source.replace('.relative_to(c.HERE)', '.relative_to(c.ROOT)'),
             str(tree / 'candidate/service_build.py'), 'exec'), service_build.__dict__)
service_build.LOCAL = out / 'resident'
service_build.run = run

builder = scope.load(tree / 'build_diag.py', 'review146_build_source')
pack = c.load(c.PRODUCT / 'pack.py', 'review146_pack')
build = c.load(c.PRODUCT / 'build.py', 'review146_link')
build.LOCAL = out / 'product-r1'
build.LOCAL.mkdir(exist_ok=True)
build.guard = lambda: scope.freeze_check()
build.run = run
build.sources = lambda: [(c.PRODUCT / 'diag.c', False),
                        (c.PRODUCT / 'src/firmware/engine/core/eng_mem.c', False)]
modules = builder.model(pack)
service_build.main()
inert, _, _ = pack.pack_model(copy.deepcopy(modules), 146)
layout = build.build(len(inert) - 256 - len(pack.STUB), lto=True)
built = build.LOCAL / 'm32r-lto'
rel = (built / 'reloc.bin').read_bytes()
identity = json.loads((scope.ROOT / 'firmware/resident_v38/local/resident/trust.json').read_text())
blob, trust, stats = pack.pack_model(modules, 146, engine=(built / 'engine.bin').read_bytes(),
    relocations=[struct.unpack_from('>II', rel, i) for i in range(0, len(rel), 8)],
    bss=layout['bss_bytes'], entry=layout['entries']['ig_bootstrap'],
    resident_id=bytes.fromhex(identity['resident_build_id']), abi_id=bytes.fromhex(identity['resident_abi_id']))
(out / 'GXRCE.DAT').write_bytes(blob)
final = scope.ROOT / 'firmware/package_v38_diag146/SD_ROOT/GXRCE.DAT'
result = dict(sha256=scope.sha(out / 'GXRCE.DAT'), bytes=len(blob), byte_equal=blob == final.read_bytes(),
              original_scripts_unchanged=True, output_redirection=True,
              metadata_path_only_replacement='.relative_to(c.HERE) -> .relative_to(c.ROOT)',
              layout=layout, inputs_unchanged=scope.freeze_check())
scope.save(out / 'result.json', result)
assert result['byte_equal'], result
print('隔离重建逐字节一致', result['sha256'])
