"""Compare the camera-rendered DNG preview with its full-size JPG."""
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'studio/src'),str(ROOT/'studio/tests')]
import numpy as np
from PIL import Image
from scipy import ndimage
from gxr_studio import audit
from gxr_studio.hdr import gain as g
from gxr_studio.meta import dng_preview_image

audit.forbid_volumes()
audit.forbid_network(True)
street=ROOT/'captures/street-g137-20261031'
folder=ROOT/'captures/a12-50/2026-10-24/stage2l-daily-R8051312-1473'
pairs=[(p,street/'dng'/(p.stem+'.DNG')) for p in sorted((street/'jpg').glob('*.JPG'))]
pairs.extend((p,p.with_suffix('.DNG')) for p in [p for p in sorted(folder.glob('*.JPG')) if p.with_suffix('.DNG').exists()][::10])
for jpg,dng in pairs:
    preview=dng_preview_image(dng,embedded_only=True)
    with Image.open(jpg) as original:
        if preview is None:
            print(json.dumps({'case':jpg.stem,'preview':None}),flush=True)
            continue
        src=np.asarray(original.resize(preview.size,Image.Resampling.BOX))
    a=g.srgb_to_linear(src)@g.LUMA
    b=g.srgb_to_linear(np.asarray(preview))@g.LUMA
    for arr in (a,b):arr[:]=ndimage.gaussian_filter(arr,.6)
    valid=(a>.01)&(a<.95)&(b>.01)&(b<.95)
    err=np.abs(np.log2(np.maximum(a,1e-5))-np.log2(np.maximum(b,1e-5)))
    print(json.dumps({'case':jpg.stem,'preview':preview.size,'correlation':float(np.mean(g._norm(a)*g._norm(b))),
                      'error_p99':float(np.percentile(err[valid],99)),'error_max':float(err[valid].max()),
                      'frac_gt_0p25':float((err[valid]>.25).mean())}),flush=True)
