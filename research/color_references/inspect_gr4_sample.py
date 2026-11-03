#!/usr/bin/env python3
"""Inspect the photographer-provided GR IV DNG, not Lightroom site JPEGs."""
import hashlib,json,sys
from pathlib import Path
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE))
from tiff_read import Tiff,exif_summary,raw_ifd,crop_info
from colour_math import dng_camera_to_xyz

def main():
    source=Path('/tmp/gxr_color_refs/downloads/gr4_hcwt_dng')
    receipt=json.loads((source/'receipt.json').read_text())
    if receipt['status']!='downloaded':raise ValueError('Complete source download required')
    data=(source/'sample.DNG').read_bytes()
    assert len(data)==receipt['bytes'] and hashlib.sha256(data).hexdigest()==receipt['sha256']
    t=Tiff(data);tags=t.tags();metadata=exif_summary(t);raw=raw_ifd(t)
    if metadata['model']!='RICOH GR IV':raise ValueError('Wrong camera model')
    ifds=[];todo=[t.root];seen=set();previews=[]
    outdir=Path('/tmp/gxr_color_refs/extracted/gr4_hcwt');outdir.mkdir(parents=True,exist_ok=True)
    while todo:
        off=todo.pop(0)
        if off in seen:continue
        seen.add(off);d=t.ifd(off);value=lambda k:d.get(k,{}).get('value')
        todo.extend(value(330) or [])
        info={'ifd_offset':off,'width':value(256),'height':value(257),'compression':value(259),'photometric':value(262),'bits':value(258)}
        jpeg=None
        if 513 in d and 514 in d:
            start=value(513)[0];length=value(514)[0];jpeg=data[start:start+length]
        elif value(259)==[7] and value(262)!=[32803] and 273 in d and 279 in d:
            jpeg=b''.join(data[start:start+length] for start,length in zip(value(273),value(279)))
        if jpeg and jpeg.startswith(b'\xff\xd8'):
            path=outdir/f'preview_{off}.jpg';path.write_bytes(jpeg)
            info['extracted_preview']={'path_scratch':str(path),'bytes':len(jpeg),'sha256':hashlib.sha256(jpeg).hexdigest()}
            previews.append(info)
        ifds.append(info)
    A,matrix=dng_camera_to_xyz(tags)
    result={'schema':'gr4-public-raw-metadata-v1','source_url':receipt['url'],
        'source_page':'https://havecamerawilltravel.com/ricoh-gr-iv-sample-images/',
        'source_sha256':receipt['sha256'],'bytes':len(data),'metadata':metadata,
        'raw_crop_xywh':crop_info(raw),'camera_to_xyz_d50':A.tolist(),'matrix_derivation':matrix,
        'ifds':ifds,'previews':previews,
        'site_jpegs_are_camera_reference':False,
        'site_jpeg_rejection':'Photographer explicitly states site images were lightly processed in Lightroom; do not pair those renders as Ricoh camera JPEGs',
        'original_camera_container':False if 'Lightroom' in (metadata['software'] or '') else None,
        'raw_mosaic_untouched':None,
        'embedded_preview_status':'已验证: Software names Lightroom; embedded preview is not accepted as a camera JPEG' if 'Lightroom' in (metadata['software'] or '') else '未知: preview processing needs independent verification',
        'priority_mode_eligible':False,
        'rejection_reasons':['ImageTone is Standard, not Positive/Negative','DNG container was written by Lightroom; website JPEGs and embedded preview cannot validate a Ricoh rendering function'],
        'golden_reference':False,'license':'David Coleman copyright; RAW provided for compatibility testing; original and previews remain only in scratch'}
    (HERE/'gr4_hcwt_metadata.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'metadata':metadata,'crop':result['raw_crop_xywh'],'previews':len(previews)},ensure_ascii=False))

if __name__=='__main__':main()
