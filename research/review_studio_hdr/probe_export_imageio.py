"""Read all twenty edited export comparisons with the macOS decoder."""
import io
import json
import subprocess
import sys
from pathlib import Path

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[1]
TMP=Path('/Volumes/Workspace/Scratch/tmp/projectricoh/review-studio-hdr')
sys.path[:0]=[str(OUT),str(ROOT/'studio/src')]
import numpy as np
from PIL import Image
from format_oracle import inspect,stops,linear_y,blocks,digest
from gxr_studio import audit
audit.forbid_volumes()
audit.forbid_network(True)
files={digest(p.read_bytes()):p for p in (TMP/'edits/exports').glob('*.jpg')}
cases=[json.loads(s) for s in (OUT/'edit_cases.jsonl').read_text().splitlines()]
cases=[r for r in cases if r['kind'] in ['actual_export','border_and_stamp','exposure_curve']]
assert len(cases)==20
exe=TMP/'format/check_imageio'
results=[]
for i,case in enumerate(cases):
    meta=case['format']
    orig=files[meta['original_sha256']]
    hdr=files[meta['hdr_sha256']]
    info,codes,rgb=inspect(orig.read_bytes(),hdr.read_bytes())
    p=subprocess.run([str(exe),str(hdr)],check=True,capture_output=True,text=True,timeout=360)
    fields=json.loads(p.stdout.splitlines()[0])
    assert fields['isoGainMap'] is not None
    assert [fields['isoGainMap']['width'],fields['isoGainMap']['height']]==info['gain_wh']
    f=TMP/('export_system_'+str(i)+'.f32')
    p=subprocess.run([str(exe),'--compare',str(orig),str(hdr),str(f)],check=True,capture_output=True,text=True,timeout=360)
    comparison=json.loads(p.stdout)
    gm=info['iso_values']
    assert abs(comparison['hdrHeadroom']/2**gm['HDRCapacityMax']-1)<0.001
    delta=stops(codes,gm)
    full=np.asarray(Image.fromarray(delta.astype(np.float32)).resize(tuple(info['image_wh']),Image.Resampling.BILINEAR))
    sdr=linear_y(rgb)
    predicted=blocks((sdr+gm['OffsetSDR'])*np.exp2(full)-gm['OffsetHDR'])
    baseline=blocks(sdr)
    values=np.fromfile(f,np.float32)
    assert values.size==2*baseline.size
    a,b=values[:baseline.size].reshape(baseline.shape),values[baseline.size:].reshape(baseline.shape)
    valid=(a>0.01)&(baseline>0.01)
    err=np.abs(np.log2(b[valid]/a[valid])-np.log2(predicted[valid]/baseline[valid]))
    p99=float(np.percentile(err,99))
    assert p99<0.15,p99
    results.append({'kind':case['kind'],'case':case.get('case',case.get('style','exposure')),'hdr_sha256':info['hdr_sha256'],
                    'image_wh':info['image_wh'],'gain_wh':info['gain_wh'],'sdr_max_abs_diff':comparison['sdrMaxAbsDiff'],
                    'headroom':comparison['hdrHeadroom'],'recognized':True,'boost_error_p99_stops':p99})
    print(json.dumps(results[-1]),flush=True)
assert audit.network_attempts()==[]
summary={'cases':len(results),'all_recognized':True,'boost_error_p99_max':max(r['boost_error_p99_stops'] for r in results),
          'sdr_max_abs_diff':max(r['sdr_max_abs_diff'] for r in results),'results':results}
(OUT/'export_imageio_cases.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps({k:v for k,v in summary.items() if k!='results'}))
