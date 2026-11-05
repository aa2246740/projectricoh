"""Freeze current delivery identities and protected inputs without changing bytes."""
from pathlib import Path
import datetime
import json
import subprocess
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import common as C
import records as R
C.setup();C.compute_gate('delivery-static-seal')
body=C.ROOT/'firmware/image_v310/local/ilaunch3';assert C.sha(body.read_bytes())=='a04f1ed40143b2c54d7f28e3af8af1f9a5ef5e115edf49eb404b8e26a53509c8'
freeze=json.loads((C.LOCAL/'engine-freeze.json').read_text())
assert all(C.sha((C.ENGINE/f).read_bytes())==digest for f,digest in freeze['source_C'].items())
inputs=json.loads((C.LOCAL/'frozen.json').read_text())['files']
frozen_drift=[r['path'] for r in inputs if C.sha((C.LOCAL/'inputs'/r['path']).read_bytes())!=r['sha256']]
assert not frozen_drift
live_drift=[r['path'] for r in inputs if C.sha((C.ROOT/r['path']).read_bytes())!=r['sha256']]
assert not live_drift,live_drift
additional=[]
for name in ('model-inputs.json','official-acros-inputs.json'):
    receipt=json.loads((C.LOCAL/name).read_text())
    for entry in receipt['files']:
        assert C.sha((C.LOCAL/'inputs'/entry['path']).read_bytes())==entry['sha256'],entry['path']
        additional.append(entry['path'])
rows=[]
for dataset in ('control','model'):
    for profile in ('test','release'):
        a=C.artifact(profile,dataset);raw=a['dat'].read_bytes();manifest=json.loads(a['manifest'].read_text());R.read_manifest(a['records'])
        assert C.sha(raw)==manifest['dat_sha256']
        assert manifest['main_request']==7628+C.D.align4(len(raw)+C.D.u32(raw,116))<=107612
        assert C.D.u32(raw,136)==manifest['code_bytes']<=69632
        if dataset=='model':
            for p in (C.PACKAGES[profile]/'local/GXRCE.DAT',C.PACKAGES[profile]/'local/SD_ROOT/GXRCE.DAT'):assert p.read_bytes()==raw
            assert json.loads((C.PACKAGES[profile]/'MANIFEST').read_text())['dat_sha256']==C.sha(raw)
        audit=json.loads((C.LOCAL/'acceptance'/dataset/('byte-audit-'+profile+'.json')).read_text())
        assert audit['DAT_sha256']==C.sha(raw) and not audit['unexplained_bytes']
        rows.append(dict(dataset=dataset,profile=profile,DAT_sha256=C.sha(raw),DAT_bytes=len(raw),main_request=manifest['main_request'],records_manifest_sha256=C.sha(a['records'].read_bytes())))
for p in (C.ENGINE/'resident').iterdir():
    if p.is_file():assert p.read_bytes()==(C.BASE/'resident'/p.name).read_bytes()
ignore=[str(C.artifact(p,'model')['dat'].relative_to(C.ROOT)) for p in ('test','release')]+['research/g157/local/metadata-rebind.json','firmware/engine_v69_g157/candidate/containers/product/diagnostic.c']
checked=subprocess.run(['git','check-ignore',*ignore],cwd=C.ROOT,text=True,capture_output=True,check=True).stdout.splitlines();assert set(checked)==set(ignore)
C.save(C.LOCAL/'delivery-static-seal.json',dict(status='PASS',utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),body_sha256=C.sha(body.read_bytes()),packages=rows,engine_C_source_identical=True,resident_copy_identical=True,frozen_input_drift=frozen_drift,live_protected_input_drift=live_drift,additional_handoff_inputs=additional,ignored=checked,compute_nice=15,camera_or_SD_access=False,network=False))
print(json.dumps(dict(status='PASS',packages=4,source_or_protected_input_drift=0)))
