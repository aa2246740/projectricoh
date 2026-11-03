#!/usr/bin/env python3
"""Generate original screen research tooling and an uncompiled experiment design."""
import json
from pathlib import Path
import sys
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import numpy as np
from colour_math import lab_rgb,rgb_lab,D65

def save(name,data):
    (HERE/name).write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False)+'\n')

PARAMS=['contrast','sharpness','vividness']+[c+'_saturation' for c in ['orange','green','blue','red','magenta']]+[c+'_hue' for c in ['orange','green','blue','red','magenta']]+['wb_axis0','wb_axis1']

def patch(ident,rgb,group,**kw):
    rgb=np.clip(np.round(np.asarray(rgb)*255),0,255).astype(int)
    return {'id':ident,'rgb8_srgb':rgb.tolist(),'nominal_display_Lab_D50':rgb_lab(rgb/255).tolist(),
            'group':group,**kw}

def lch(ident,L,C,h,group):
    direction=np.array([0,np.cos(np.radians(h)),np.sin(np.radians(h))])
    def rgb(c):return lab_rgb(np.array([L,0,0])+c*direction,white=D65)
    c=C
    if np.any(rgb(c)<0) or np.any(rgb(c)>1):
        lo,hi=0.,C
        for _ in range(40):
            m=(lo+hi)/2
            if np.all((rgb(m)>=0)&(rgb(m)<=1)):lo=m
            else:hi=m
        c=lo
    return patch(ident,rgb(c),group,requested_LCh_D65=[L,C,h],gamut_fitted_C=c)

def main():
    mem=[('skin_dark',38,22,42),('skin_medium',55,24,45),('skin_light',72,20,48),
         ('skin_warm',65,29,55),('skin_cool',62,20,30),('skin_shadow',30,15,45),
         ('sky_light',75,22,255),('sky_medium',55,30,265),('sky_deep',35,24,280),
         ('foliage_sun',60,35,125),('foliage_dark',30,20,145),('foliage_olive',48,25,105),
         ('orange_object',62,45,65),('red_object',45,40,25),('blue_object',45,35,280),('magenta_object',50,35,335)]
    pages=[]
    for validation in (False,True):
        pre='V' if validation else 'T'
        vals=np.linspace(4,251,32) if validation else np.linspace(0,255,32)
        pp=[patch(f'{pre}N{i+1:02d}',np.repeat(v/255,3),'neutral',neutral_rank=i) for i,v in enumerate(vals)]
        for name,L,C,h in mem:
            group='memory_'+name.split('_')[0] if name.split('_')[0] in ['skin','sky','foliage'] else 'object_colour'
            pp.append(lch(pre+'_'+name,L+(2 if validation else 0),C,h+(4 if validation else 0),group))
        pages.append({'id':pre+'1','purpose':'acceptance' if validation else 'training',
                      'title':('验收' if validation else '测量')+' · 灰阶与常见颜色','patches':pp})
        for j,L in enumerate(([25,50,80] if validation else [35,55,75]),2):
            pp=[]
            for C in [12,25,40]:
                for h in range(0,360,30):
                    pp.append(lch(f'{pre}{j}_C{C}_H{h}',L,C,h+(15 if validation else 0),'hue_sweep'))
            for k,v in enumerate([24,64,104,152,200,236]):pp.append(patch(f'{pre}{j}_N{k}',np.repeat(v/255,3),'neutral',neutral_rank=k))
            for name,Lm,Cm,hm in mem[:3]+[mem[7],mem[9],mem[10]]:
                group='memory_'+name.split('_')[0]
                pp.append(lch(f'{pre}{j}_{name}',Lm+(2 if validation else 0),Cm,hm+(4 if validation else 0),group))
            pages.append({'id':pre+str(j),'purpose':'acceptance' if validation else 'training',
                          'title':('验收' if validation else '测量')+f' · 明度 L* {L}','patches':pp})
    for page in pages:
        assert len(page['patches'])==48
        for i,p in enumerate(page['patches']):p.update(row=i//8,col=i%8,roi_fraction_of_patch=[.3,.3,.7,.7])
    pages.sort(key=lambda x:x['id'])
    chart={'schema':'gxr-emissive-chart-v1','author':'Original research tooling written for this task',
           'not_a_vendor_reference':True,'encoding':'8-bit CSS sRGB, SDR; nominal Lab is a design coordinate, not measured emitted colour',
           'layout':{'rows':6,'cols':8,'gutter_css_px':8,'min_patch_css_px':[140,100],
                     'sample':'central 40% only; find patch corners from the photographed screen, not nominal viewport pixels'},
           'pages':pages,'photometric_absolute_truth':False,'do_not_use_nominal_display_lab_to_calibrate_sensor':True}
    save('screen_chart.json',chart)
    html='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>GXR 屏幕测量工具</title>
<style>*{box-sizing:border-box}html,body{margin:0;width:100%;height:100%;overflow:hidden;background:#808080;color:#fff;font:14px system-ui}body{padding:26px 20px 20px}.bar{position:absolute;left:20px;right:20px;top:2px;height:22px;display:flex;justify-content:space-between;align-items:center}.grid{height:100%;display:grid;grid-template-columns:repeat(8,1fr);grid-template-rows:repeat(6,1fr);gap:8px}.patch{position:relative;min-width:0;min-height:0}.tag{position:absolute;left:4px;top:3px;color:#fff;background:#000b;font:10px monospace;padding:1px 3px}.tools{position:fixed;left:30px;bottom:30px;background:#222;padding:22px;max-width:650px;box-shadow:0 3px 18px #0006;z-index:2;line-height:1.7}.tools.hidden{display:none}button{padding:7px 12px;margin:4px;border:1px solid #aaa;border-radius:3px;font:inherit;cursor:pointer}.notice{font-size:12px}#warning{color:#fff;background:#800;position:absolute;top:50%;left:10%;right:10%;text-align:center;padding:30px;display:none}.edge{display:none;background:#fff;height:100%;color:#000;padding:30px}.edge.active{display:block}.edge.active+.grid{display:none}.slant{width:43%;height:70%;background:#000;transform:rotate(5deg);display:inline-block;margin-right:10%}.texture{display:inline-block;width:35%;height:70%;background:repeating-linear-gradient(90deg,#000 0 2px,#fff 2px 4px)}</style>
<div class="bar"><span id="title"></span><span>研究工具 · ← → 换页 · F 全屏 · H 菜单</span></div>
<div id="edge" class="edge"><p>锐度专页 E1 · 这页请重新对准焦点 · 不参加颜色拟合</p><div class="slant"></div><div class="texture"></div></div><main id="grid" class="grid"></main>
<aside id="tools" class="tools"><h2>GXR 屏幕测量工具</h2><p>这是本次研究编写的离线色块工具，不是 Ricoh 原厂标准图。测量页 T1–T4，验收页 V1–V4。每次换页后等 3 秒。</p><p>固定 Internet &amp; Web (sRGB) 参考预设；关闭 True Tone、Night Shift、自动亮度。不要用截图软件、照片编辑器或 HDR 滤镜调整这页。</p><button id="prev">上一页</button><button id="next">下一页</button><button id="full">全屏</button><button id="hide">收起菜单 H</button><p class="notice">先拍 8 对试拍。照相前收起菜单。8 列 × 6 行，取色只读色块中央，不读角落标签。此页无网络请求，不自动换页。</p></aside><div id="warning">窗口太小。请全屏，或把浏览器缩放改为 100%。</div>
<script>const data=__DATA__;let index=0;const list=data.pages;const grid=document.getElementById('grid');const menu=document.getElementById('tools');function draw(){const isEdge=index===list.length;document.getElementById('edge').classList.toggle('active',isEdge);grid.style.display=isEdge?'none':'grid';if(isEdge){document.getElementById('title').textContent='E1 锐度';return}const p=list[index];document.getElementById('title').textContent=p.id+' '+p.title;grid.replaceChildren(...p.patches.map(x=>{const d=document.createElement('div');d.className='patch';d.dataset.id=x.id;d.style.backgroundColor='rgb('+x.rgb8_srgb.join(',')+')';const s=document.createElement('span');s.className='tag';s.textContent=x.id;d.append(s);return d}));document.getElementById('warning').style.display=(grid.clientWidth/8<140||grid.clientHeight/6<100)?'block':'none'}function step(n){index=(index+n+list.length+1)%(list.length+1);draw()}async function fullscreen(){if(!document.fullscreenElement)await document.documentElement.requestFullscreen();else await document.exitFullscreen()}document.getElementById('prev').onclick=()=>step(-1);document.getElementById('next').onclick=()=>step(1);document.getElementById('hide').onclick=()=>menu.classList.add('hidden');document.getElementById('full').onclick=fullscreen;document.addEventListener('keydown',e=>{if(['ArrowRight',' ','ArrowLeft'].includes(e.key)){e.preventDefault();step(e.key==='ArrowLeft'?-1:1)}if(e.key.toLowerCase()==='h')menu.classList.toggle('hidden');if(e.key.toLowerCase()==='f')fullscreen();if(/^[1-8]$/.test(e.key)){index=Number(e.key)-1;draw()}});window.addEventListener('resize',draw);draw();window.gxrChart={data,getPage:()=>index,getROIs:()=>[...grid.children].map(x=>({id:x.dataset.id,box:x.getBoundingClientRect().toJSON()}))};</script></html>'''
    (HERE/'screen_chart.html').write_text(html.replace('__DATA__',json.dumps(chart,ensure_ascii=False)))
    H=np.array([[1]])
    while len(H)<16:H=np.block([[H,H],[H,-H]])
    design=H[:,1:]
    assert np.linalg.matrix_rank(np.column_stack([np.ones(16),design]))==16
    def settings(overrides=None,mode='Color',te=None):
        d={p:(0 if p.startswith('wb_') else 5) for p in PARAMS};d.update(overrides or {})
        return {'base_mode':mode,'selector_hex':{'Color':'04','B&W':'03','B&W toned':'06'}[mode],
                'te_tone':te,'te_numeric_encoding':None,'controls_display':d}
    bankA=[]
    for i,row in enumerate(design):
        bankA.append({'slot':i+1,'label':f'A{i+1:02d}','settings':settings({p:int(s)+(0 if p.startswith('wb_') else 5) for p,s in zip(PARAMS,row)}),
                      'purpose':'orthogonal local main-effects design; interactions are aliased'})
    bspec=[('Color baseline',{},'Color',None),('Color contrast 1',{'contrast':1},'Color',None),
           ('Color contrast 9',{'contrast':9},'Color',None),('Color vividness 1',{'vividness':1},'Color',None),
           ('Color vividness 9',{'vividness':9},'Color',None),('Color sharpness 1',{'sharpness':1},'Color',None),
           ('Color sharpness 9',{'sharpness':9},'Color',None),('B&W baseline',{},'B&W',None),
           ('B&W contrast 1',{'contrast':1},'B&W',None),('B&W contrast 9',{'contrast':9},'B&W',None)]
    bspec += [(f'TE {tone}',{},'B&W toned',tone) for tone in ['Sepia','Red','Green','Blue','Purple']]
    bspec += [('TE Sepia contrast 9',{'contrast':9},'B&W toned','Sepia')]
    bankB=[{'slot':i+1,'label':f'B{i+1:02d} '+name,'settings':settings(d,m,t),'purpose':name} for i,(name,d,m,t) in enumerate(bspec)]
    save('calibration_bank_design.json',{'schema':'gxr-experiment-design-not-recipe-v1','compile':False,'deployable':False,
        'encoding_boundary':'All values are display-domain experiment factors. No raw enums, binary bank or camera writes are generated.',
        'base_modes_from_task_brief_not_camera_verified':True,'parameter_order':PARAMS,
        'bank_A':bankA,'bank_B':bankB,'linear_design':{'runs':16,'factors':15,'rank_with_intercept':16,'X_transpose_X':(H.T@H).tolist(),
        'limitations':'16 runs identify 15 local main effects plus intercept only under an additive approximation; two-factor interactions are fully aliased. Bank B baseline/extremes detect lack of fit, not all interactions. Add single-control confirmations around final candidates.'},
        'capture_plan':{'pilot_pairs':8,'pilot_sequence':['B01:T1','B01:T2','B01:T3','B01:T4','B08:T1','B08:T3','B11:T3','B01:T1 repeat'],
        'full_screen_pairs':134,'full_screen_explanation':'A01..A16 and B01..B16 each T1..T4 = 128; B01 T1,T3 at beginning and end = 4; B01 T1 exposure -1EV,+1EV = 2',
        'sharpness_pairs':6,'sharpness_explanation':'E1 in focus, B01/B06/B07 each twice; outside colour calibration',
        'real_object_pairs':8,'real_object_explanation':'Two daylight object arrangements, B01/B08/B11/B15 each once; do not fit acceptance arrangements',
        'full_calibration_pairs_including_sharpness_and_real_objects':148,'pilot_is_separate':True,
        'acceptance_pairs_after_fitting':36,'acceptance_explanation':'two looks × (V1..V4 + two new object scenes) × three non-consecutive repeats',
        'slots_require_separate_authorized_compilation_and_camera_validation':True}})
    acceptance={'schema':'gxr-gr-screen-acceptance-v1','status':'NOT_RUN','scope':'screen-measured alignment to a frozen GR reference function plus small daylight object set',
        'primary_looks':['Positive Film','Negative Film'],'reference_generation_candidates':['GR III','GR IIIx','GR IV'],
        'reference_generation_must_be_selected_and_frozen_before_fitting':True,
        'reference_prerequisites':['Executable GR camera-RGB to sRGB JPEG reference including WB/matrix/curve/sector order, version/hash and parameter state',
            'Reference renderer checked on genuine same-exposure GR RAW/JPEG, with error budget recorded; partial firmware tables alone are insufficient',
            'Both sensors DNG matrices and neutral/exposure convention frozen; any sensor bridge is explicitly a colorimetric approximation'],
        'reference_formula':'target_i = F_GR(frozen_exposure_scale * B_common_white_frozen * raw_GXR_i); B = inv(A_GR_common_white) * A_GXR_common_white = M_GR(T_common) * inv(M_GXR(T_common)); one common illuminant/adaptation for both sensors, independent of candidate recipe WB/AsShotNeutral; no per-image or per-patch tuning at acceptance',
        'comparison_space':'JPEG sRGB EOTF -> XYZ D65 -> Bradford D50 -> CIELAB D50, CIEDE2000 kL=kC=kH=1',
        'thresholds':{'all_patches':{'de00_median_max':1.0,'de00_p90_max':2.0,'de00_max':3.0},
            'neutrals':{'de00_median_max':0.6,'de00_p90_max':1.2,'de00_max':2.0},
            'each_memory_group_skin_sky_foliage':{'de00_median_max':1.0,'de00_p90_max':2.0,'de00_max':3.0},
            'neutral_tone_ramp':{'abs_delta_L_median_max':0.5,'abs_delta_L_p90_max':1.0,'abs_delta_L_max':2.0,
                 'luminance_order_reversals_allowed':0,'reference':'GR target L*, including its intended cast/contrast, not nominal screen ramp'},
            'repeatability':{'same_patch_across_repeats_de00_p90_max':0.5},
            'reference_renderer_same_gr_pair':{'de00_median_max':0.5,'de00_p90_max':1.0},
            'valid_patch_coverage_min':0.95,'forbid_new_channel_clipping_where_reference_has_headroom':True},
        'units_of_acceptance':{'looks':2,'screen_pages':['V1','V2','V3','V4'],'new_daylight_object_scenes':2,'repeats':3,'total_raw_jpeg_pairs':36,
            'minimum_valid_patches_per_screen_frame':46,'minimum_object_rois_per_frame':12,
            'memory_group_coverage':'skin/sky/foliage have >=3 ROIs each across the two real-object scenes; actual hand/leaf/sky preferred; substitutes retain object-only labels',
            'neutrals_per_object_scene_min':3},
        'decision':'Every look and every scene must pass across all 3 repeats; also report pooled equal-patch metrics. No pixel-count weighting, no pooling scenes to hide a failure.',
        'exclusions':'Only predeclared RAW-clipped, misregistered, glare, boundary or below-noise patches. Record every exclusion; >5% missing on any screen frame fails quality gate.',
        'not_proven_by_this':'Reflective spectral equivalence, a human visibility JND for all observers, grain/texture/local contrast, other ISO/WB/illumination, or original-GR firmware authenticity without renderer validation',
        'current_blockers':['No complete validated GR reference function delivered yet','No screen control sweep or held-out acceptance captures'],
        'claim_when_passed':'Meets the declared screen-measured alignment thresholds for the frozen GR reference, selected look settings, ISO 200 and tested scenes only'}
    save('acceptance.json',acceptance)
    print('Wrote eight 48-patch pages, an edge page, two 16-slot experimental banks and acceptance contract')

if __name__=='__main__':main()
