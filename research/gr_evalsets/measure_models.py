#!/usr/bin/env python3
"""Predeclared flat-block tests, chart tests and model-only target coverage."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import engine as e
import numpy as np
from PIL import Image, ImageDraw
from scipy.optimize import least_squares, minimize_scalar

NAMES = ['dark_skin','light_skin','blue_sky','foliage','blue_flower','bluish_green',
         'orange','purplish_blue','moderate_red','purple','yellow_green','orange_yellow',
         'blue','green','red','yellow','magenta','cyan',
         'white','neutral_8','neutral_6_5','neutral_5','neutral_3_5','black']
# Coordinates are geometry measurements from the local camera JPEGs, not colour fits.
# Corners correspond to chart (row0,col0), (row0,col5), (row3,col0), (row3,col5).
CORNERS = {
    'gr3_still': [(2724,3280),(3206,3288),(2722,3568),(3205,3574)],
    'gr3_portrait': [(2919,3143),(2933,2795),(3127,3154),(3139,2808)],
    'gr3x_still': [(2811,3109),(3265,3115),(2806,3381),(3260,3386)],
}
REGIONS = {
    'gr3_still': {'fabric':(250,100,2840,2550),'thread':(3100,280,5280,1560),
                  'crayons':(450,2700,1640,3170)},
    'gr3_portrait': {'face':(1500,620,2110,1430),'hands':(2700,3240,3750,3790),
                     'red_flowers':(3680,1550,4260,1820),'blue_flowers':(3730,1270,4150,1550),
                     'foliage':(4700,100,5960,2940),'hair':(1080,150,1860,1630)},
    'gr3x_still': {'fabric':(300,100,2900,2430),'thread':(3140,270,5310,1490),
                   'crayons':(660,2530,1720,3050)},
}


def region(name, box):
    x, y = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
    return next((key for key, (x0,y0,x1,y1) in REGIONS.get(name, {}).items() if x0 <= x < x1 and y0 <= y < y1), 'other')


def chart_boxes(name):
    if name == 'bastibe':
        ref = e.read(e.VENDOR / 'color_references/gr3_reference_measurements.json')
        return [(p['chart_label'], p['jpeg_roi_xyxy']) for p in ref['variants']['standard']['patches']]
    p00,p05,p30,p35 = np.array(CORNERS[name], float)
    result=[]
    for row in range(4):
        for col in range(6):
            a,b = row/3, col/5
            x,y = (1-a)*((1-b)*p00+b*p05)+a*((1-b)*p30+b*p35)
            radius = 12 if name == 'gr3_portrait' else 20
            x,y = (np.rint(np.array([x,y])/2)*2).astype(int)
            result.append((NAMES[row*6+col], [x-radius,y-radius,x+radius,y+radius]))
    return result


def sample(data, box, label, name):
    x0,y0,x1,y1 = (np.array(box)//2).astype(int)
    raw = data['rgb'][y0:y1,x0:x1].astype(float)
    jpg = data['jpeg_half'][y0:y1,x0:x1].astype(float)
    target = jpg.mean((0,1))/255
    lab = e.cm.rgb_lab(target)
    clip = data['clip'][y0:y1,x0:x1]
    raw_mean = raw.mean((0,1))
    prediction = e.render(raw_mean,data['neutral'])
    pixel_prediction = e.render(raw,data['neutral']).mean((0,1))
    radius = np.hypot(((x0+x1)/2-data['rgb'].shape[1]/2)/(data['rgb'].shape[1]/2),
                      ((y0+y1)/2-data['rgb'].shape[0]/2)/(data['rgb'].shape[0]/2))/np.sqrt(2)
    return dict(label=label,box=box,region=region(name,box),raw=raw_mean,jpeg=target,lab=lab,
                u=float(e.u_of(raw_mean,data)),u_no_be=float(e.u_of(raw_mean,data)/2**float(data['be'])),
                jpeg_luma=float(target@e.pm.RGB_LUMA*255),jpeg_std=jpg.std((0,1)),
                jpeg_min=float(jpg.min()),jpeg_max=float(jpg.max()),raw_clip_fraction=float(clip.mean()),
                raw_min=float(raw.min()),prediction=prediction,pixel_prediction=pixel_prediction,
                de00=float(e.cm.delta_e00(e.cm.rgb_lab(prediction),lab)),
                averaging_de00=float(e.cm.delta_e00(e.cm.rgb_lab(prediction),e.cm.rgb_lab(pixel_prediction))),
                hue=float(np.degrees(np.arctan2(lab[2],lab[1]))%360),chroma=float(np.hypot(lab[1],lab[2])),
                radius=float(radius))


def flat_samples(data,name):
    # One disjoint 32x32 full-resolution ROI per 64x64 cell, no error-based filtering.
    h,w = data['rgb'].shape[:2]
    result=[]
    for y in range(16,h-16,32):
        for x in range(16,w-16,32):
            jpg=data['jpeg_half'][y-8:y+8,x-8:x+8]
            if jpg.max() >= 251 or np.max(jpg.std((0,1))) > 3.:
                continue
            if data['clip'][y-8:y+8,x-8:x+8].any():
                continue
            rec=sample(data,[2*x-16,2*y-16,2*x+16,2*y+16],f'flat_{x}_{y}',name)
            if 10 <= rec['lab'][0] <= 95 and rec['raw_min'] > 0:
                result.append(rec)
    return result


def aggregate(records, field='de00'):
    return e.stats([r[field] for r in records])


def distributions(records):
    hues={}
    for lo in range(0,360,30):
        selected=[r for r in records if lo <= r['hue'] < lo+30 and r['chroma'] >= 8]
        hues[f'{lo:03d}_{lo+30:03d}']=aggregate(selected)
    lights={}
    for lo,hi in [(10,30),(30,50),(50,70),(70,95.01)]:
        lights[f'{lo:g}_{hi:g}']=aggregate([r for r in records if lo <= r['lab'][0] < hi])
    balanced=[]
    for h in range(-1,12):
        for light in range(5):
            group=[r for r in records if (int(r['hue']//30) if r['chroma']>=8 else -1)==h
                   and min(4,int(r['lab'][0]//20))==light]
            # Keep spatial scan order and evenly spread retained observations in each stratum.
            if len(group)>12:
                group=[group[i] for i in np.linspace(0,len(group)-1,12,dtype=int)]
            balanced+=group
    return dict(all_flat=aggregate(records),colour_flat=aggregate([r for r in records if r['chroma']>=8]),
                hue_light_balanced=aggregate(balanced),hue_bins=hues,lightness_bins=lights,
                regions={k:aggregate([r for r in records if r['region']==k]) for k in sorted({r['region'] for r in records})},
                radial={k:aggregate([r for r in records if lo<=r['radius']<hi]) for k,lo,hi in [('center',0,.35),('middle',.35,.65),('edge',.65,1.1)]},
                averaging_error=aggregate(records,'averaging_de00'))


def fit_neutrals(chart, data):
    # Six chart neutrals only. This diagnostic must not replace the frozen holdout result.
    neutral=chart[-6:]
    raw=np.array([r['raw'] for r in neutral]);target=np.array([r['jpeg'] for r in neutral])
    solve=minimize_scalar(lambda ev:np.mean(((e.render(raw,data['neutral'],exposure=2**ev)-target)@e.pm.RGB_LUMA)**2),bounds=(-2,2),method='bounded')
    def residual(params):
        ev,r,b=params
        return (e.render(raw,data['neutral'],exposure=2**ev,wb_extra=np.array([2**r,1,2**b]))-target).ravel()
    rgbfit=least_squares(residual,[solve.x,0,0],bounds=([-2,-.5,-.5],[2,.5,.5]),xtol=1e-11,gtol=1e-11,ftol=1e-11)
    # Gain/exposure nuisance search is restricted to neutrals and uses a finite grid.
    best=None
    for gain in range(4096,20001,128):
        s=minimize_scalar(lambda ev:np.mean(((e.render(raw,data['neutral'],exposure=2**ev,gain=gain)-target)@e.pm.RGB_LUMA)**2),bounds=(-2,2),method='bounded')
        if best is None or s.fun<best[0]:best=(s.fun,gain,s.x)
    return dict(exposure_ev=float(solve.x),wb_rgb_fit_ev=rgbfit.x,
                gain_exposure_fit=dict(gain=best[1],exposure_ev=float(best[2]),neutral_luma_rmse=float(best[0]**.5*255)))


def apply_diagnostic(records,data,fit):
    raw=np.array([r['raw'] for r in records]);actual=np.array([r['lab'] for r in records])
    def metric(**kwargs):return e.stats(e.cm.delta_e00(e.cm.rgb_lab(e.render(raw,data['neutral'],**kwargs)),actual))
    ev,r,b=fit['wb_rgb_fit_ev'];g=fit['gain_exposure_fit']
    return dict(exposure_only=metric(exposure=2**fit['exposure_ev']),
                exposure_wb=metric(exposure=2**ev,wb_extra=np.array([2**r,1,2**b])),
                gain_exposure=metric(exposure=2**g['exposure_ev'],gain=g['gain']))


def annotate(name,chart,records):
    path=e.DATA/e.SCENES[name][1]
    with Image.open(path) as im:
        im=im.convert('RGB');im.thumbnail((1500,1000));draw=ImageDraw.Draw(im)
        scale=im.width/6000
        for rec in records:
            box=tuple(int(v*scale) for v in rec['box']);draw.rectangle(box,outline='#20df70')
        for rec in chart:
            box=tuple(int(v*scale) for v in rec['box']);draw.rectangle(box,outline='#ff2040',width=2)
        im.save(e.LOCAL/f'{name}_rois.jpg',quality=93)


def style_checks(bastibe,data):
    result={}
    for mode,path in e.STYLE_FILES.items():
        md=e.read(e.LOCAL/f'{mode}_metadata.json');state=e.model_state(mode,md['maker']['image_control_0x0247'])
        with Image.open(e.DATA/path) as im:jpg=np.asarray(im.convert('RGB'))
        records=[]
        for source in bastibe:
            x0,y0,x1,y1=source['box'];target=jpg[y0:y1,x0:x1].mean((0,1))/255
            pred=e.render(source['raw'],data['neutral'],mode,state)
            standard_lab=e.cm.rgb_lab(source['prediction']);pred_lab=e.cm.rgb_lab(pred)
            actual_lab=e.cm.rgb_lab(target)
            # Transfer the model's Lab relative effect to the measured Standard.
            relative=source['lab']+(pred_lab-standard_lab)
            records.append(dict(label=source['label'],de00=float(e.cm.delta_e00(pred_lab,actual_lab)),
                                relative_de00=float(e.cm.delta_e00(relative,actual_lab)),
                                predicted_lab=pred_lab,actual_lab=actual_lab))
        result[mode]=dict(absolute=aggregate(records),relative_lab_addition=aggregate(records,'relative_de00'),
                          software=md['software'],sliders=state['sliders'],
                          toning={k:v for k,v in md['maker']['image_control_0x0247'].items() if 'toning' in k or 'tone' in k},
                          per_patch=records)
    e.dump(e.LOCAL/'style_checks.json',result)
    return {k:{x:v[x] for x in ('absolute','relative_lab_addition','software','sliders','toning')} for k,v in result.items()}


def coverage(records):
    sectors={'red':(0,45),'magenta':(315,360),'blue':(240,285),'purple':(285,315)}
    result={}
    for name,(lo,hi) in sectors.items():
        rows=[r for r in records if lo<=r['hue']<hi and r['chroma']>=20]
        if not rows:result[name]={'n':0};continue
        result[name]=dict(n=len(rows),max_chroma=float(max(r['chroma'] for r in rows)),
                          chroma_p90=float(np.percentile([r['chroma'] for r in rows],90)),
                          L_range=[float(min(r['lab'][0] for r in rows)),float(max(r['lab'][0] for r in rows))],
                          standard_error=aggregate(rows),regions={k:sum(r['region']==k for r in rows) for k in sorted({r['region'] for r in rows})})
    return result


def small_semantic_samples(data,name,std_limit=3.,per_stratum=4):
    """Fixed 12px windows retain flat dye/flower areas without averaging cloth texture."""
    candidates=[]
    for category,(x0,y0,x1,y1) in REGIONS.get(name,{}).items():
        for y in range((y0//2)+3,(y1//2)-3,12):
            for x in range((x0//2)+3,(x1//2)-3,12):
                jpg=data['jpeg_half'][y-3:y+3,x-3:x+3]
                if jpg.max()>=251 or np.max(jpg.std((0,1)))>std_limit:
                    continue
                if data['clip'][y-3:y+3,x-3:x+3].any():continue
                lab=e.cm.rgb_lab(jpg.mean((0,1))/255)
                C=np.hypot(lab[1],lab[2]);hue=np.degrees(np.arctan2(lab[2],lab[1]))%360
                if not 10<=lab[0]<=95 or C<8:continue
                candidates.append(dict(category=category,box=[2*x-6,2*y-6,2*x+6,2*y+6],
                                       stratum=(category,int(hue//15),int(lab[0]//15)),chroma=float(C)))
    selected=[]
    for key in sorted({r['stratum'] for r in candidates}):
        rows=[r for r in candidates if r['stratum']==key]
        # Up to four spatially separated representatives, including the highest chroma.
        ordered=sorted(rows,key=lambda r:-r['chroma'])
        group=[]
        for rec in ordered:
            center=np.array(rec['box'][:2])
            if all(np.linalg.norm(center-np.array(r['box'][:2]))>=48 for r in group):group.append(rec)
            if len(group)==per_stratum:break
        selected+=group
    return [sample(data,r['box'],f'small_{std_limit:g}_{i}_{r["category"]}',name) for i,r in enumerate(selected)],len(candidates)


def radial_diagnostic(data,records,chart,semantic):
    state=e.model_state('standard')
    greys=[r for r in records if r['chroma']<8 and 25<r['lab'][0]<85]
    train=[r for r in greys if (r['box'][0]//64+r['box'][1]//64)%2==0]
    test=[r for r in greys if (r['box'][0]//64+r['box'][1]//64)%2==1]
    if len(train)<12:return None
    raw=np.array([r['raw'] for r in train]);target=np.array([r['jpeg'] for r in train])
    linear=(raw/data['neutral'])@(state['front']/256).T*state['e']
    input_j=np.interp(target*16384,state['curve'],np.arange(256)*16)/4095
    scales=np.sum(input_j*linear,axis=1)/np.sum(linear**2,axis=1)
    r2=np.array([r['radius']**2 for r in train])
    design=np.array([r2**k for k in range(4)]).T
    fit=least_squares(lambda p:design@p-np.log2(scales),[0,0,0,0],loss='soft_l1',f_scale=.03)
    def evaluate(rows):
        if not rows:return e.stats([])
        radius=np.array([r['radius'] for r in rows])
        ev=sum(fit.x[k]*radius**(2*k) for k in range(4))
        pred=e.render(np.array([r['raw'] for r in rows]),data['neutral'],exposure=2**ev[:,None])
        return e.stats(e.cm.delta_e00(e.cm.rgb_lab(pred),np.array([r['lab'] for r in rows])))
    return dict(evidence_level='scene_fitted_diagnostic_not_frozen_validation',train_neutral_count=len(train),
                coefficients_ev_by_r2_power=fit.x,neutral_holdout=evaluate(test),all_flat=evaluate(records),
                chart_all=evaluate(chart),chart_colour_18=evaluate(chart[:18]),semantic=evaluate(semantic),
                EV_center=float(fit.x[0]),EV_corner=float(fit.x.sum()),
                residual_ev=e.stats(np.abs(design@fit.x-np.log2(scales))))


def main():
    output={'criteria':dict(full_roi=32,full_stride=64,jpeg_max_channel_std=3.,jpeg_max_strictly_below=251,
                            lower_channel_clamp_allowed=True,semantic_full_roi=12,semantic_full_stride=24,
                            L_range=[10,95],raw_clipped_pixels_allowed=0,selection_uses_model_error=False), 'scenes':{}}
    scene_records={}
    for name in e.SCENES:
        data,md=e.load_scene(name)
        chart=[sample(data,box,label,name) for label,box in chart_boxes(name)]
        flats=flat_samples(data,name)
        semantic,candidates=small_semantic_samples(data,name)
        material,material_candidates=small_semantic_samples(data,name,10.,2)
        record=dict(chart=chart,flats=flats,semantic=semantic,semantic_candidates=candidates,
                    material=material,material_candidates=material_candidates)
        if name!='bastibe':
            fit=fit_neutrals(chart,data)
            record['diagnostic_fit']=fit
            diagnostics={k:apply_diagnostic(v,data,fit) for k,v in [('chart',chart),('colour_18',chart[:18]),('flats',flats)]}
        else:fit=None;diagnostics=None
        scene_records[name]=record
        e.dump(e.LOCAL/f'{name}_samples.json',record)
        output['scenes'][name]=dict(chart=aggregate(chart),chart_colours=aggregate(chart[:18]) if name!='bastibe' else None,
                                    distribution=distributions(flats),diagnostic_fit=fit,diagnostics=diagnostics,
                                    coverage=coverage(flats),chart_averaging=aggregate(chart,'averaging_de00'))
        output['scenes'][name]['semantic']=dict(candidates=candidates,retained=len(semantic),coverage=coverage(semantic),
            all=aggregate(semantic),regions={k:aggregate([r for r in semantic if r['region']==k]) for k in REGIONS.get(name,{})},
            averaging=aggregate(semantic,'averaging_de00'))
        output['scenes'][name]['radial_diagnostic']=radial_diagnostic(data,flats,chart,semantic)
        output['scenes'][name]['material_exploration']=dict(
            excluded_from_flat_validation=True,jpeg_std_limit=10.,retained=len(material),candidates=material_candidates,
            coverage=coverage(material),all=aggregate(material),averaging=aggregate(material,'averaging_de00'))
        annotate(name,chart,flats)
        print(name,e.jsonable(output['scenes'][name]['chart']),e.jsonable(output['scenes'][name]['distribution']['all_flat']),flush=True)
    data,_=e.load_scene('bastibe')
    output['styles']=style_checks(scene_records['bastibe']['chart'],data)
    for name,rec in scene_records.items():
        data,_=e.load_scene(name)
        rows=rec['flats']+rec['semantic']+rec['material']
        raw=np.array([r['raw'] for r in rows]);standard=e.cm.rgb_lab(e.render(raw,data['neutral']))
        targets={mode:e.cm.rgb_lab(e.render(raw,data['neutral'],mode)) for mode in ('positive','negative')}
        e.dump(e.LOCAL/f'{name}_model_only_targets.json',dict(
            evidence_level='model_inference_unvalidated_for_styled_IR',training_approved=False,
            schema='gr-evalsets-model-candidates/1',units='absolute CIELAB D50 from encoded sRGB, kL=kC=kH=1',
            gxr_training_pair_available=False,metering_anchor_available=False,
            metadata=f'{name}_metadata.json',sample_source=f'{name}_samples.json',
            note='Captured RAW exposure and WB are retained; no grey-card or GXR exposure normalization.',
            measured_styled_IR_available=False,labels=[r['label'] for r in rows],raw=raw,
            standard_lab=standard,targets=targets))
    e.dump(e.LOCAL/'model_summary.json',output)
    print('style_checks',e.jsonable(output['styles']),flush=True)


if __name__=='__main__':main()
