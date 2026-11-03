#!/usr/bin/env python3
"""Freeze a common-white RAW bridge, separate from each image's rendered WB."""
import hashlib,json,sys
from pathlib import Path
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE))
from tiff_read import Tiff
from colour_math import common_white_sensor_bridge,D65

def main():
    gxr=json.loads((HERE/'gxr_characterisation.json').read_text())
    path=next(Path(p['dng']['path']) for p in gxr['pairs'] if Path(p['dng']['path']).stem=='R8051136')
    data=path.read_bytes();g=Tiff(data).tags()
    inputs={'GXR':{'path':str(path),'sha256':hashlib.sha256(data).hexdigest()}}
    bridges=[]
    for model,path,note in [
        ('GR III',Path('/tmp/gxr_color_refs/downloads/bastibe_gr3_dng/Target.DNG'),'Original-camera DNG, firmware 1.60'),
        ('GR IV',Path('/tmp/gxr_color_refs/downloads/gr4_hcwt_dng/sample.DNG'),'Lightroom-written DNG; auxiliary colorimetric model, not independently verified original Ricoh matrices')]:
        data=path.read_bytes();r=Tiff(data).tags();B,desc=common_white_sensor_bridge(g,r,D65)
        inputs[model]={'path':str(path),'sha256':hashlib.sha256(data).hexdigest(),'source_note':note}
        bridges.append({'model':model,**desc})
    result={'schema':'common-white-camera-bridge-v1','inputs':inputs,'bridges':bridges,
        'white_assumption':'D65 is the planned screen reference white, not measured emitted chromaticity. Pilot neutral RAW may refine one common white before fitting, then freeze it.',
        'not_a_golden_reference':True,'exposure_scale_status':'Unknown until training neutral convention is selected; do not fit it again at acceptance',
        'why_not_use_per_file_rendering_matrices':'inverse(A_GR_as_shot)*A_GXR_as_shot introduces different WB adaptations when their neutrals differ; retain those prior products as diagnostics only'}
    (HERE/'common_white_sensor_bridges.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    print('Derived fixed-D65 native ColorMatrix bridges for GR III and auxiliary GR IV DNG model; no camera look rendered')

if __name__=='__main__':main()
