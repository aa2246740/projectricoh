#!/usr/bin/env python3
"""Read only the parallel worker's derived JSON, never firmware binaries."""
import hashlib,json,struct
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]

def main():
    inputs=[];variants=[]
    for name in ['gr3-2.10-tables.json','gr3x-1.60-tables.json','gr4-1.11-tables.json']:
        path=ROOT/'research/gr_firmware/data'/name
        data=path.read_bytes();d=json.loads(data)
        inputs.append({'path':str(path.relative_to(ROOT)),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()})
        selected=[]
        for t in d['tables']:
            if t['mode'] not in ['Standard','Positive Film','Negative Film'] or not t['id'].endswith('-look-matrix'):continue
            raw=struct.pack('<9h',*t['values'])
            assert hashlib.sha256(raw).hexdigest()==t['sha256']
            assert all(sum(t['values'][i:i+3])==8192 for i in [0,3,6])
            selected.append({k:t[k] for k in ['id','mode','association','vma','payload_offset','size','format','sha256','values','scale','normalized','row_sums']})
        variants.append({'model':d['model'],'firmware':d['version'],'source_payload_sha256_reported_by_worker':d['payload_sha256'],
                         'look_matrix_constraints':selected,'complete_camera_rgb_to_jpeg':False})
    out={'schema':'gr-firmware-partial-constraints-v1','evidence':'已验证: derived JSON values reproduce block SHA256 and row sums. Firmware provenance/mode selection relies on the parallel report; raw firmware not accessed here.',
         'source_report':'../gr_firmware/REPORT.md','upstream_inputs':inputs,'variants':variants,
         'chart_targets':None,'why_not_rendered':'Raw look matrices are intermediate operators; final tone generation/default sliders/gains/domain are incomplete. Applying them to sRGB or XYZ would invent a target.',
         'GR4_extra_positive':'Separate MultiAxial bounds, bank selectors, controls and 2160-byte matrix block per upstream report; full execution semantics unverified',
         'selection_recommendation':'First close and validate GR III/IIIx because independent GR III chart pairs exist; retain GR IV as separate candidate',
         'not_executed':'No firmware, downloaded code, camera, installer or existing project script'}
    (HERE/'gr_firmware_constraints.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
    print('Collected 9 verified partial matrix constraints for 3 firmware variants; no invented chart transform')

if __name__=='__main__':main()
