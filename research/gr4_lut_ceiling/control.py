"""Natural same-RAW Standard/Positive pair hidden in the renamed TEST control."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import runtime as rt
from runtime import np
from style import Dense,relative,feature
from isp import model
from PIL import Image
from scipy.ndimage import uniform_filter


def main():
    m=model();d=Dense('positive')
    tiff=rt.module('control_tiff','research/gr_incamera_dev/tiff_io.py')
    source=rt.ROOT/'captures/contrib/2026-10-19/gr4-modes/positive.DNG'
    control=rt.ROOT/'captures/contrib/2026-10-25-gr4-wechat/extracted/GR4/R0000101/R0000101.DNG'
    streams=[]
    geometries=[]
    for path in (source,control):
        t=tiff.Tiff(rt.inp(path).read_bytes());seg=t.segments(t.raw)[0]
        streams.append(rt.hashlib.sha256(t.data[seg['offset']:seg['offset']+seg['capacity']]).hexdigest())
        geometries.append(t.geometry())
    assert streams[0]==streams[1] and geometries[0]==geometries[1]
    jpg=control.with_name('R0000101 Std.JPG')
    tm=rt.module('control_metadata','research/contrib_gr_analysis/tiff_makernote.py')
    metadata=[]
    for path in (jpg,source.with_suffix('.JPG')):
        t,_=tm.jpeg_exif_tiff(rt.inp(path).read_bytes());_,at,note,_,_=tm.maker_note_bytes(t)
        entries,decoded=tm.decode_gr3_family(t,at)
        metadata.append(dict(tone=decoded['image_tone'],controls=decoded['image_control_0x0247'],
                             wb=decoded['white_balance_0x0019'],
                             wb_rggb=next((e['value'] for e in entries if e['tag']==0x0201),None)))
    keys=('saturation','hue','high_low_key','contrast','contrast_highlight','contrast_shadow','sharpness','shading','clarity')
    assert all(metadata[0]['controls'][k]==0 for k in keys)
    expected=dict(saturation=0,hue=0,high_low_key=-1,contrast=3,contrast_highlight=-1,contrast_shadow=-2,sharpness=0,shading=0,clarity=0)
    assert all(metadata[1]['controls'][k]==v for k,v in expected.items())
    wb_match=metadata[0]['wb_rggb']==metadata[1]['wb_rggb']
    a=rt.arrays('research/gr_pairs/local/samples/gr4b_positive.npz')
    p=rt.arrays(rt.LOCAL/'natural/gr4b_positive_metadata_BE_new_radial.npz')
    take=p['source_index'];sx,sy=a['xy'][take].T
    with Image.open(jpg) as im:
        im.load();orientation=im.getexif().get(274,1);image=np.asarray(im.convert('RGB'),np.float32)
    assert orientation==1 and image.shape[:2]==(geometries[0]['crop_wh'][1],geometries[0]['crop_wh'][0])
    h,w=image.shape[:2]
    half=image.reshape(h//2,2,w//2,2,3).mean(axis=(1,3))
    mean=np.column_stack([uniform_filter(half[...,c],5)[sy,sx] for c in range(3)])
    sd=np.column_stack([np.sqrt(np.maximum(uniform_filter(half[...,c]**2,5)[sy,sx]-mean[:,c]**2,0)) for c in range(3)])
    valid=(mean>2).all(1)&(mean<253).all(1)&(sd.max(1)<3.5)
    std=rt.lab(mean);observed=p['observed'];raw=p['raw_wb']
    values,raw_support,_=d.raw_function(feature(raw))
    direct,std_support,_=d.std_function(std/[20.,30.,30.])
    transferred=relative(std,values[:,:3],values[:,3:])
    x=raw@np.linalg.inv(d.T).T*(320/d.anchor)
    gxr_base=rt.lab(m.predict('04',x))
    actual_target=relative(gxr_base,std,observed)
    inferred_target=relative(gxr_base,values[:,:3],values[:,3:])
    results=[]
    for region,geographic in [('all',np.ones(len(take),bool)),('central_r_lt_035',a['r2'][take]<.35**2)]:
        use=valid&raw_support&std_support&geographic
        target_difference=rt.cm.delta_e00(inferred_target[use],actual_target[use])
        base_error=rt.cm.delta_e00(gxr_base[use],actual_target[use])
        results.append(dict(region=region,n=int(use.sum()),
                    RAW_to_Standard=rt.stats(rt.cm.delta_e00(values[use,:3],std[use])),
                    RAW_to_Positive=rt.stats(rt.cm.delta_e00(values[use,3:],observed[use])),
                    measured_Std_to_Positive=rt.stats(rt.cm.delta_e00(direct[use],observed[use])),
                    relative_RAW_transfer=rt.stats(rt.cm.delta_e00(transferred[use],observed[use])),
                    target_sampling_only_score=rt.score(target_difference,base_error),
                    assumes_exact_GXR_bridge=True,actual_GXR_same_scene_pixels=False))
    rt.dump('natural/control_same_RAW.json',dict(source=source,returned_control=control,standard_jpeg=jpg,
                identical_RAW_stream_sha256=streams[0],metadata=metadata,
                all_points=len(take),flat_Std_points=int(valid.sum()),results=results,
                training=False,exposure_refit=False,WB_refit=False,standard_actual_not_inferred=True,
                different_rendering_body=True,one_natural_scene_only=True,
                JPEG_WB_levels_match=wb_match,strict_same_WB_style_acceptance=wb_match,
                diagnostic_only_because_WB_mismatch=not wb_match))
    np.savez_compressed(rt.LOCAL/'natural/control_same_RAW.npz',source_index=take,std=std,positive=observed,
                        predicted_direct=direct,predicted_relative=transferred,raw_wb=raw,
                        valid=valid,raw_support=raw_support,std_support=std_support,r2=a['r2'][take],
                        gxr_base=gxr_base,actual_target=actual_target,inferred_target=inferred_target)
    print('natural same-RAW',[(r['region'],r['n'],r['measured_Std_to_Positive'],r['relative_RAW_transfer']) for r in results],flush=True)


if __name__=='__main__':main()
