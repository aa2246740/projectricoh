"""Write the probe2 field report and static scientific figures from receipts."""
import os
import sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
OUT=HERE/'local/field_probe2_20261103'
TMP=Path('/Volumes/Workspace/Scratch/tmp/projectricoh/probe2-field-20261103')
for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','VECLIB_MAXIMUM_THREADS','MKL_NUM_THREADS'):
    os.environ[key]='1'
os.environ.update(TMPDIR=str(TMP),PYTHONDONTWRITEBYTECODE='1')
sys.dont_write_bytecode=True
import argparse
import csv
import hashlib
import json
import math
import plistlib
import re
import shutil
import subprocess
import time
import numpy as np
from PIL import Image,ImageDraw,ImageFont


def read(name):return json.loads((OUT/name).read_text())
def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
    return h.hexdigest()
def plain(value):
    if isinstance(value,dict):return {str(k):plain(v) for k,v in value.items()}
    if isinstance(value,(tuple,list)):return [plain(v) for v in value]
    if isinstance(value,(np.ndarray,np.generic)):return plain(value.tolist())
    return value
def dump(name,value):(OUT/name).write_text(json.dumps(plain(value),ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def num(x,n=3):return f'{x:.{n}f}'
def vec(values,n=3):return ' / '.join(num(float(x),n) for x in values)
def rng(values,n=1):return '–'.join(num(float(x),n) for x in values)
def name(key):
    if key=='A':return 'A'
    if key=='unknown':return 'unknown'
    return ('P1 '+key[0]+'−2') if key.endswith('N') else ('P2 '+key[0]+'+2')


FONT='/System/Library/Fonts/Supplemental/Arial.ttf'
small=ImageFont.truetype(FONT,17);font=ImageFont.truetype(FONT,21);title=ImageFont.truetype(FONT,27)
COLORS={'R':'#b84236','G':'#237a57','B':'#315fa5'}


def axes(draw,box,xlim,ylim,xticks,yticks,xlabel,ylabel):
    l,t,w,h=box
    xp=lambda x:l+(x-xlim[0])/(xlim[1]-xlim[0])*w
    yp=lambda y:t+h-(y-ylim[0])/(ylim[1]-ylim[0])*h
    for y in yticks:
        draw.line((l,yp(y),l+w,yp(y)),fill='#dedede');draw.text((l-38,yp(y)-10),f'{y:g}',font=small,fill='#444444')
    for x in xticks:
        draw.line((xp(x),t,xp(x),t+h),fill='#eeeeee');draw.text((xp(x)-17,t+h+7),f'{x:g}',font=small,fill='#444444')
    draw.rectangle((l,t,l+w,t+h),outline='#777777')
    draw.text((l,t+h+34),xlabel,font=small,fill='black');draw.text((l,t-31),ylabel,font=font,fill='black')
    return xp,yp


def figures():
    points=read('measure-0.5.json')['points'];model=read('model.json');xs=np.array(model['xs'])
    old=json.loads((ROOT/'research/probe_pack_r1/local/ramp_field_20261103/measure-0.5.json').read_text())['points']
    im=Image.new('RGB',(1710,1380),'white');d=ImageDraw.Draw(im)
    d.text((40,18),'Probe2: local kernels on the conditional A-inverse axis',font=title,fill='black')
    d.text((40,54),'Filled: Y-inferred magnitude. Outline triangles: RGB projection. Grey: earlier +16 Y. Black: nominal two-code tent.',font=small,fill='black')
    for ri,node in enumerate((8,16,19)):
        lo,hi={8:(65,180),16:(440,905),19:(780,1280)}[node]
        ticks={8:[80,120,160],16:[500,650,800],19:[800,1000,1200]}[node]
        for ci,ch in enumerate('RGB'):
            box=(75+ci*560,145+ri*410,460,292)
            xp,yp=axes(d,box,(lo,hi),(-1,5),ticks,[-1,0,1,2,3,4,5],'Conditional input',f'{ch}, node {node}: inferred curve codes')
            left,peak,right=xs[node-1:node+2];xx=np.linspace(lo,hi,200);tent=2*np.maximum(0,np.minimum((xx-left)/(peak-left),(right-xx)/(right-peak)))
            d.line([(xp(x),yp(y)) for x,y in zip(xx,tent)],fill='black',width=2)
            key=ch+('N' if node==16 else 'D')
            rr=[r for r in points if r['label']==key and r['gray'] and not r['excluded'] and (node!=16 or r['phase']=='p1')]
            if node==16:
                for row in old:
                    if row['channel']==ch and row['gray'] and not row['excluded'] and lo<row['conditioned_input']<hi and -1<row['q_y']<5:
                        px,py=xp(row['conditioned_input']),yp(row['q_y']);d.rectangle((px-2,py-2,px+2,py+2),fill='#bbbbbb')
            for row in rr:
                x=row['conditioned_input'];sign=-1 if node==16 else 1
                if not lo<x<hi:continue
                y=sign*row['q_y'];z=sign*row['q_rgb'];px=xp(x)
                if -1<y<5:
                    py=yp(y);d.ellipse((px-3,py-3,px+3,py+3),fill=COLORS[ch])
                if -1<z<5:
                    py=yp(z);d.polygon([(px,py-4),(px-4,py+3),(px+4,py+3)],outline='#222222')
    im.save(OUT/'kernel-response.png')
    comps=[r for r in read('primary-components.json') if r['frame']=='pooled']
    order=[('RN',16),('GN',16),('BN',16),('RD',8),('RD',19),('GD',8),('GD',19),('BD',8),('BD',19)]
    im=Image.new('RGB',(1710,670),'white');d=ImageDraw.Draw(im)
    d.text((40,20),'Final-JPEG component response / original prediction',font=title,fill='black')
    d.text((40,58),'Local diagnostics on active grey samples; these are not replacements for DAT parameter units.',font=small,fill='black')
    for c,component in enumerate(('Y','Cb','Cr')):
        box=(75+c*560,145,460,365);xp,yp=axes(d,box,(-.7,8.7),(-.3,2.7),[],[0,1,2],component,'Local response coefficient')
        d.line((box[0],yp(1),box[0]+box[2],yp(1)),fill='#111111',width=2)
        for i,(key,node) in enumerate(order):
            row=next(r for r in comps if r['label']==key and r['node']==node);value=row['gain_Y_Cb_Cr'][c]
            x=xp(i);y=yp(value);zero=yp(0);d.rectangle((x-15,min(y,zero),x+15,max(y,zero)),fill=COLORS[key[0]])
            d.text((x-20,y-23 if value>=0 else y+3),num(value,2),font=small,fill='black')
            d.text((x-21,box[1]+box[3]+10),f'{key[0]}{node}',font=small,fill='black')
    d.text((40,610),'16 is a negative step. Nodes 8 and 19 are positive steps. See report for ROI/reference sensitivity and sample counts.',font=small,fill='black')
    im.save(OUT/'component-response.png')
    cc=read('color_sensitivity.json')
    panels=[('R-16 / skin',['R8051935'],'skin'),('B-16 / blue',['R8051937'],'blue'),
            ('R+19 / skin',['R8051949','R8051951'],'skin'),('B+19 / blue',['R8051947','R8051953'],'blue')]
    im=Image.new('RGB',(1710,1050),'white');d=ImageDraw.Draw(im)
    d.text((40,20),'Colour patches: measured and predicted Y / Cb / Cr changes',font=title,fill='black')
    d.text((40,58),'Colour bars: measured. Grey bars: predicted. Black whiskers: ROI / nearest-A / repeat range, not a confidence interval.',font=small,fill='black')
    for panel,(label,frames,patch) in enumerate(panels):
        box=(85+(panel%2)*840,155+(panel//2)*440,690,295);xp,yp=axes(d,box,(-.65,2.65),(-2.2,2.3),[],[-2,-1,0,1,2],'Native JPEG components',label)
        rows=[r for r in cc if r['frame'] in frames and r['patch']==patch]
        obs=np.mean([r['observed_ycc'] for r in rows],axis=0);pred=np.mean([r['predicted_ycc'] for r in rows],axis=0)
        low=np.min([r['ROI_observed_min'] for r in rows]+[r['nearest_A_observed_ycc'] for r in rows],axis=0)
        high=np.max([r['ROI_observed_max'] for r in rows]+[r['nearest_A_observed_ycc'] for r in rows],axis=0)
        for c,comp in enumerate(('Y','Cb','Cr')):
            x=xp(c);zero=yp(0)
            for center,value,color in ((x-20,obs[c],COLORS[label[0]]),(x+20,pred[c],'#aaaaaa')):
                y=yp(value);d.rectangle((center-17,min(y,zero),center+17,max(y,zero)),fill=color)
            d.line((x-20,yp(low[c]),x-20,yp(high[c])),fill='black',width=2)
            d.line((x-25,yp(low[c]),x-15,yp(low[c])),fill='black',width=2);d.line((x-25,yp(high[c]),x-15,yp(high[c])),fill='black',width=2)
            d.text((x-13,box[1]+box[3]+10),comp,font=font,fill='black')
    im.save(OUT/'color-patches.png')
    drift=read('drift.json');rep=[r for r in read('primary-repeatability.json') if r['node']=='all']
    groups=[r['first'][-4:]+'/'+r['last'][-4:] for r in drift]+[r['frames'][0][-4:]+'/'+r['frames'][1][-4:] for r in rep]
    vv=[r['corrected_ycc_rms'] for r in drift]+[r['ycc_rms'] for r in rep]
    im=Image.new('RGB',(1650,650),'white');d=ImageDraw.Draw(im)
    d.text((40,20),'A drift after per-patch RAW correction, and paired P2 effect differences',font=title,fill='black')
    box=(90,130,1470,350);xp,yp=axes(d,box,(-.6,len(groups)-.4),(0,.22),[],[0,.05,.1,.15,.2],'A pairs first, then R / G / B P2 repeats','RMS in native JPEG component codes')
    for i,values in enumerate(vv):
        for c,col in enumerate(('#ae7425','#315fa5','#b84236')):
            x=xp(i)+(c-1)*28;y=yp(values[c]);d.rectangle((x-11,y,x+11,yp(0)),fill=col)
        d.text((xp(i)-65,495),groups[i],font=small,fill='black')
    d.text((90,560),'Y = ochre; Cb = blue; Cr = red. Each P2 repeat has two frames. Input changes are still part of these paired differences.',font=small,fill='black')
    im.save(OUT/'drift-repeatability.png')
    print(json.dumps(dict(status='PASS',figures=4)))


def tables():
    identities=read('assignments.json')['frames'];points=read('measure-0.5.json')['points']
    with (OUT/'frame-identities.csv').open('w',newline='') as stream:
        writer=csv.writer(stream);writer.writerow(['frame','page','response_identity','confidence','markers','heldout_edge_p95_pixels_at_1000','best_amplitude','feature_rmse'])
        for r in identities:writer.writerow([r['frame'],r['phase'],name(r['label']),r['confidence'],r['marker_count'],r['heldout_edge_95'],r['best_amplitude'],r['feature_rmse']])
    columns=['frame','label','phase','channel','patch','gray','raw_wb','conditioned_input','q_y','q_rgb','q_nominal','observed_rgb','observed_ycc','predicted_rgb','predicted_ycc','reference_frames']
    with (OUT/'main-points.csv').open('w',newline='') as stream:
        writer=csv.writer(stream);writer.writerow(columns)
        for row in points:writer.writerow([json.dumps(row[k],ensure_ascii=False) if isinstance(row[k],(list,dict)) else row[k] for k in columns])
    columns=['label','node','fraction','response','kind','peak','half_left','half_right','FWHM','amplitude','rmse','near_parameter_bound']
    with (OUT/'kernel-fits.csv').open('w',newline='') as stream:
        writer=csv.writer(stream);writer.writerow(columns)
        for row in read('primary-free_kernels.json'):writer.writerow([row[k] for k in columns])
    coverage=read('primary-coverage.json');symmetry=read('symmetry.json')
    handoff=dict(verdict='部分可用',input_manifest_sha256=read('inputs.json')['manifest_sha256'],
        probe_dat_sha256=sha(ROOT/'firmware/package_v39_g154_probe2/local/SD_ROOT/GXRCE.DAT'),
        frame_identities={r['frame']:dict(label=r['label'],confidence=r['confidence'],page=r['phase']) for r in identities},
        probe_definitions={key:dict(channel=key[0],nodes=[16] if key.endswith('N') else [8,19],delta=-2 if key.endswith('N') else 2)
            for key in ('RN','GN','BN','RD','GD','BD')},A_scope='Response-compatible baseline; not a literal menu/DAT identity proof.',
        native_curve_control=dict(negative16_confirmed=True,positive8_19_confirmed=True,names_RGB_confirmed=True),
        quantitative_L1_full_color_accepted=False,continuous_full_color_range_accepted=None,
        accepted_scope='Candidate generation and measured local controls only; sampled ranges are not continuous quantitative acceptance.',
        sampled_gray_ranges=coverage,diagnostic_component_coefficients=read('primary-components.json'),
        coefficient_scope='Final JPEG response / transferred-model prediction; not new DAT units or a global channel multiplier.',
        interpolation=dict(working='piecewise_linear',unique_hardware_algorithm_identified=False,
            issue='Y and RGB-projection rankings differ; B node8 Y favours nearest while RGB favours continuous curves.'),
        node16_symmetry=symmetry,quantization_phase_identified=False,
        color_failures=['P1 R-16 skin Cb is near zero rather than predicted positive response.',
            'B-16 and B+19 blue-patch Cr changes oppose the transferred model; +19 repeats agree.'],
        recipe_redo_actions=['Keep channel names and literal two-code DAT steps.',
            'Calibrate separate Y/Cb/Cr local derivatives versus input brightness, hue and signed step.',
            'Do not apply one global channel gain or one fixed chroma matrix.',
            'Treat node16 plus/minus comparison across different capture times as conditional.'],
        next_capture=dict(shots_to_replace_missing_identities=0,matched_plus_minus16_minimum=8,
            plus_minus_requires_new_DAT=True,optional_second_screen_code_phase_total=16,
            quantization_algorithm_also_needs_static_rounding_evidence=True))
    dump('recipe_redo_handoff.json',handoff)
    print(json.dumps(dict(status='PASS',identity_rows=21,measurement_rows=len(points),handoff=True)))


def validate():
    inputs=read('inputs.json');assert len(inputs['files'])==42
    for row in inputs['files']:assert sha(ROOT/row['file'])==row['sha256']
    assert sha(ROOT/'captures/probe2-field-20261103/SHA256SUMS')==inputs['manifest_sha256']
    for path,wanted in read('protected.json').items():assert sha(ROOT/path)==wanted,path
    for path,wanted in read('model.json')['inputs'].items():assert sha(ROOT/path)==wanted,path
    sym=read('symmetry.json');assert sha(ROOT/sym['old_positive_measurement'])==sym['old_sha256']
    assigned=read('assignments.json');assert assigned['no_order_or_count_prior']
    metadata=read('metadata.json');assert len(metadata)==21
    for row in metadata:
        assert abs(row['dng']['exposure_s']-1/15)<1e-12 and row['dng']['iso']==200
        for field in ('selector','sliders_raw','wb_shotinfo','as_shot_neutral'):
            assert row['dng'][field]==metadata[0]['dng'][field]
        assert row['quantization']['0'][0]==row['quantization']['1'][0]==1
    rows=assigned['frames'];assert len(rows)==21 and sum(r['label']=='unknown' for r in rows)==3
    assert [r['frame'] for r in rows if r['label']=='unknown']==['R8051944','R8051945','R8051946']
    confirmation=read('confirmation.json');assert len(confirmation)==12 and all(r['assigned']==r['best_RGB_template'] for r in confirmation)
    assert all(len(r['all_ROI_labels'])==1 for r in rows if r['label']!='unknown')
    for fraction in ('0.35','0.5','0.65'):
        points=read('measure-'+fraction+'.json')['points'];assert len(points)==624 and not any(r['excluded'] for r in points)
        assert not any(r['frame'] in {'R8051944','R8051945','R8051946'} for r in points)
        for r in points:assert len(r['observed_rgb'])==len(r['observed_ycc'])==3
    for n in range(1934,1955):
        frame=read(f'frames/R805{n}.json');assert frame['frame']==f'R805{n}'
        assert frame['raw']['sensor_payload_sha256'] and len(frame['location']['markers'])==4
        expected_count=2 if 1944<=n<=1946 else 4
        assert frame['location']['marker_count_used']==expected_count
    for p in OUT.glob('timing-*.json'):
        v=json.loads(p.read_text());assert v['status']=='PASS' and v['nice']>=15 and v['seconds']<1800
    env=read('environment.json');assert env['nice']>=15 and env['numerical_threads']==1 and env['max_compute_processes']==2
    assert len(read('primary-repeatability.json'))==9
    for filename,count in [('frame-identities.csv',21),('main-points.csv',624),('kernel-fits.csv',72)]:
        with (OUT/filename).open(newline='') as stream:assert len(list(csv.DictReader(stream)))==count,filename
    handoff=read('recipe_redo_handoff.json');assert handoff['verdict']=='部分可用' and not handoff['quantitative_L1_full_color_accepted']
    rerun=read('extraction-rerun.json');assert rerun['frames']==21 and rerun['all_bytes_equal'] and rerun['changed']==[]
    assert read('independent-color-check.json')['status']=='PASS'
    for figure in ('kernel-response.png','component-response.png','color-patches.png','drift-repeatability.png'):
        with Image.open(OUT/figure) as im:assert im.width>=1600 and im.height>=600;im.verify()
    result=dict(status='PASS_WITH_LIMITS',verdict='部分可用',input_files_checked=42,frames=21,identified=18,unknown=3,
        phase_counts={'p1':sum(r['phase']=='p1' for r in rows),'p2':sum(r['phase']=='p2' for r in rows)},
        corner_counts={'four':18,'top_two_only':3},ROI_fractions=[.35,.5,.65],measurement_rows_each=624,
        independent_RGB_confirmations=12,saturation_exclusions=0,source_hashes_unchanged=True,
        no_order_prior=True,material_limits=['Three cropped frames remain ambiguous after flat-ROI salvage.',
            'No same-scene positive/negative node16 pair.', 'Conditional A-inverse input is not direct ISP state.',
            'Quantization order and colour derivatives are not closed.'])
    dump('acceptance.json',result);print(json.dumps(result,ensure_ascii=False))


def independent():
    """Check decisive colour signs from RGB means without RAW/model correction."""
    metadata={r['frame']:r for r in read('metadata.json')}
    def seconds(frame):
        hh,mm,ss=map(int,metadata[frame]['dng']['time'].split()[1].split(':'));return hh*3600+mm*60+ss
    matrix=np.array([[.299,.587,.114],[-.168736,-.331264,.5],[.5,-.418688,-.081312]])
    cases=[('R8051935','skin','R8051934','R8051938'),('R8051937','blue','R8051934','R8051938'),
        ('R8051947','blue','R8051943','R8051950'),('R8051953','blue','R8051950','R8051954')]
    results=[]
    for frame,patch,first,last in cases:
        def item(stem):return next(r for r in read('frames/'+stem+'.json')['patches']['0.5'] if r['id']==patch)
        p,a,b=item(frame),item(first),item(last);alpha=(seconds(frame)-seconds(first))/(seconds(last)-seconds(first))
        rgb=np.array(p['jpeg_mean'])-(1-alpha)*np.array(a['jpeg_mean'])-alpha*np.array(b['jpeg_mean'])
        native=np.array(p['native_ycc_mean'])-(1-alpha)*np.array(a['native_ycc_mean'])-alpha*np.array(b['native_ycc_mean'])
        computed=matrix@rgb
        if patch=='blue':assert np.sign(computed[2])==np.sign(native[2]) and abs(computed[2])>.15
        else:assert abs(computed[1])<.2 and abs(native[1])<.2
        results.append(dict(frame=frame,patch=patch,direct_RGB_delta=rgb,standard_RGB_to_YCbCr_delta=computed,
            native_JPEG_YCbCr_delta=native,no_RAW_correction=True,no_transferred_model=True))
    dump('independent-color-check.json',dict(status='PASS',rows=results,
        purpose='Independent component-sign check using standard RGB conversion; not the primary native-Y measurements.'))
    print(json.dumps(plain(dict(status='PASS',checks=len(results),Cr_signs=[r['standard_RGB_to_YCbCr_delta'][2] for r in results]))))


def report():
    acceptance=read('acceptance.json');assert acceptance['status']=='PASS_WITH_LIMITS'
    clean=read('cleanup.json');assert clean['status']=='PASS' and clean['temporary_directory_absent'] and not TMP.exists()
    identities=read('assignments.json')['frames'];metadata=read('metadata.json')
    cover=read('primary-coverage.json');comps=[r for r in read('primary-components.json') if r['frame']=='pooled']
    kernels=read('primary-free_kernels.json');shapes=read('primary-shape_fits.json');sym=read('symmetry.json')['rows']
    drift=read('drift.json');rep=[r for r in read('primary-repeatability.json') if r['node']=='all']
    colors=read('color_sensitivity.json');sens=read('component_sensitivity.json')
    frame_table=[]
    for row,meta in zip(identities,metadata):
        conf={'high':'高','medium':'中','unknown':'不判定'}[row['confidence']]
        feature='残差超界' if row['label']=='unknown' else ('最大 '+num(max(v['amplitude_used'] for v in row['fits'].values()),2) if row['label']=='A' else num(row['fits'][row['label']]['amplitude'],2))
        marker='仅 TL/TR' if row['marker_count']==2 else '四标'
        frame_table.append(f"| {row['frame']} | {meta['dng']['time'].split()[1]} | {row['phase'].upper()} | {name(row['label'])} | {conf} | {feature} | {marker} / {row['heldout_edge_95']:.2f} |")
    coverage_table=[]
    for node in (8,16,19):
        cells=[]
        for ch in 'RGB':
            key=ch+('N' if node==16 else 'D');r=next(r for r in cover if r['label']==key and r['node']==node)
            cells.append(f"{r['left_points']} / {r['right_points']}；{rng(r['active_raw_wb_range'])}")
        coverage_table.append('| '+str(node)+' | '+' | '.join(cells)+' |')
    free_table=[]
    for node in (8,16,19):
        for ch in 'RGB':
            key=ch+('N' if node==16 else 'D')
            yy=next(r for r in kernels if r['fraction']=='0.5' and r['label']==key and r['node']==node and r['kind']=='linear' and r['response']=='q_y')
            rgb=next(r for r in kernels if r['fraction']=='0.5' and r['label']==key and r['node']==node and r['kind']=='linear' and r['response']=='q_rgb')
            free_table.append(f"| {ch}{'−' if node==16 else '+'} / {node} | {vec([yy['peak'],yy['FWHM'],yy['amplitude']],2)} | {vec([rgb['peak'],rgb['FWHM'],rgb['amplitude']],2)} |")
    shape_table=[]
    for node in (8,16,19):
        for ch in 'RGB':
            key=ch+('N' if node==16 else 'D');r=next(r for r in shapes if r['fraction']=='0.5' and r['label']==key and r['node']==node and r['response']=='q_y' and r['branch']=='mean')
            by={v['shape']:v for v in r['fits']}
            shape_table.append(f"| {ch} / {node} | "+' | '.join(num(by[k]['rmse']) for k in ('linear_tent','pchip_difference','nearest_node','linear_floor','linear_round'))+' |')
    component_table=[]
    for node in (8,16,19):
        for ch in 'RGB':
            key=ch+('N' if node==16 else 'D');r=next(r for r in comps if r['label']==key and r['node']==node)
            rr=next(r for r in sens if r['label']==key and r['node']==node)
            yvalues=[v['gain'][0] for v in rr['estimates']]+[v['nearest_A_gain'][0] for v in rr['estimates']]
            component_table.append(f"| {ch}{'−' if node==16 else '+'} / {node} | {vec(r['gain_Y_Cb_Cr'])} | {min(yvalues):.3f}–{max(yvalues):.3f} | {r['n']} |")
    symmetry_table=[]
    for r in sym:
        symmetry_table.append(f"| {r['channel']} | {r['positive']['gain_active_no_intercept']:.3f} | {r['negative_primary']['gain_active_no_intercept']:.3f} | {r['primary_negative_positive_ratio']:.3f} |")
    drift_table=[]
    for r in drift:
        drift_table.append(f"| {r['first'][-4:]}→{r['last'][-4:]} | {r['elapsed_s']:.0f} | {vec(r['raw_percent_median'],2)} | {vec(r['corrected_ycc_rms'])} |")
    late=next(r for r in drift if r['first']=='R8051950')
    middle=next(r for r in drift if r['first']=='R8051943')
    repeat_table=[]
    for r in rep:
        repeat_table.append(f"| {r['label'][0]}，{r['frames'][0][-4:]}↔{r['frames'][1][-4:]} | {r['n']} | {vec(r['rgb_rms'])} | {vec(r['ycc_rms'])} |")
    color_table=[]
    for frame,patch in [('R8051935','skin'),('R8051937','blue'),('R8051949','skin'),('R8051951','skin'),('R8051947','blue'),('R8051953','blue')]:
        r=next(r for r in colors if r['frame']==frame and r['patch']==patch)
        color_table.append(f"| {frame[-4:]}，{name(r['label'])} / {'肤色' if patch=='skin' else 'B 色块'} | {r['conditioned_input']:.1f} | {r['q_nominal']:.2f} | {vec(r['observed_ycc'])} | {vec(r['predicted_ycc'])} |")
    low=[r for r in read('rough_band_check.json') if r['Y_band']==[30,80]]
    low_table=['| '+r['frame'][-4:]+' | '+vec(r['direct_channel_minus_mean'])+' | '+vec(r['RAW_corrected_channel_minus_mean'])+' |' for r in low]
    input_digest=read('inputs.json')['manifest_sha256'];dat_digest=sha(ROOT/'firmware/package_v39_g154_probe2/local/SD_ROOT/GXRCE.DAT')
    text=f'''部分可用

21 张中，18 张能按响应识别，1944–1946 保留 unknown。1934–1938 是 A、R−2、G−2、B−2、A；1947–1954 是 B+2、G+2、R+2、A、R+2、G+2、B+2、A，支持机主和用户对最后八张的判断。另有一组明确结果：1939–1943 拍的是 P2 页面，但条目响应是 A、P1 R−2、G−2、B−2、A，不是 P2 双节点正向。

负向节点 16 和正向节点 8/19 都确实受控，重复性足以确认条目和局部响应。严格正负对称、量化相位和全颜色定量模型仍未闭合。肤色的 Cb 缺口继续存在；这次激励到的 B 色块还确认了 Cr 方向错误。不能用一个通道倍率修正当前模型。

| 本轮问题 | 能回答到什么程度 |
| --- | --- |
| P1 负向符号与通道 | 可以确认三路都按负向局部响应。 |
| 节点 16 严格正负对称 | 部分支持；旧正向与新负向非同场，G 约有 13% 诊断幅度差。 |
| 量化相位、floor/round 顺序 | 不能确定，候选排名随输入分布和输出反推方式变化。 |
| P2 节点 8/19 | 两个分离响应带及重复成立；原模型的分量幅度不能直接推广。 |
| 肤色与 B 色块 | 都被激励；实测足以确认当前色度模型有缺口。 |
| 是否补拍这 21 张 | 不必为条目覆盖补拍；进一步同场正负定标最少 8 张，需新的 ±16 DAT。 |

## 素材和拍摄条件

素材为 `captures/probe2-field-20261103/` 的 R8051934–R8051954，共 21 组 DNG＋JPG。独立核对同目录 SHA256SUMS 的 42 项，并在交付前复核。拍摄时间为相机记录的 19:23:50–19:26:20。

机主提供的条件为 MOUNT、35mm f/2 七片式 Mandler 设计复刻版手动镜头，实际 f/5.6。21 张 EXIF 都是 1/15 秒、ISO 200；白平衡字段和 AsShotNeutral 全组相同。光圈字段为 0，实际光圈采用机主提供的 f/5.6。选择器均为 Standard，滑杆显示均为对比 5、锐度 6、鲜艳度 5，其余滑杆也一致。EXIF 不能区分这些深层探针条目。

模型按本地探针 2 DAT `{dat_digest}` 的实际条目展开：P1 改零基节点 16，分别 −2；P2 同时改节点 8、19，分别单通道 +2。P2 的 +2 不是节点 16 的正向对照。照片不含 DAT 哈希，文件身份沿用所交付的探针定义与机主的拍摄背景。

## 逐帧定位与识别方法

每张独立从角标外框和编码模板求单应变换，再用偶数位置灰块的边界微调，奇数位置的边界作留出检查。以下边界误差按图像宽 1000 像素计。角标识别包括几何角位置与模板相关，不宣称每个模糊码格都逐位解码成功。

18 张的四个角标都在画面内且能定位。1944–1946 只有 TL/TR；BL/BR 和下方三个彩块不可见，名义第七行灰块也落到 Dock／可见图板之外。两上角标不能充分约束下方取样，这三张的部分 ROI 混入了边缘或其它内容。

页面身份用已知屏幕灰码到 RAW 的光传递残差判断。仅用灰码排序相关不够，因为两页灰块的排序相近。条目识别先比较逐块 RAW 与 JPG 反演得到的局部特征，允许每帧有随亮度变化的背景项；每张都检验六个带符号模板，不限制每类张数，不输入拍摄计划或口述顺序。主测取色面中央 50%，35% 和 65% 独立复核。12 张可识别扰动随后用实际 RGB 差分模板再次确认，结果全部相同。

“高／中”只指在 A 和六种已知探针之间的判定把握，不是标定后的概率。A 指与基线响应相容，照片不能证明菜单中具体选的是哪一个像素等效基底，也不能把 EXIF Standard 当成 A 身份证据。

| 照片 | 相机时间 | 页面 | 响应判定 | 置信度 | 归一化主特征幅度 | 角标 / 留出边界 P95 |
| --- | --- | --- | --- | --- | ---: | --- |
{chr(10).join(frame_table)}

四标指 TL/TR/BL/BR 均可定位。“最大”是六个探针模板的最大正向拟合幅度；扰动行只列被判定模板的幅度，1 约为该模板的名义响应。幅度经过背景拟合，不能当作新 DAT 单位。完整六模板分数及三种 ROI 在 [assignments.json](local/field_probe2_20261103/assignments.json) 和 [逐帧 CSV](local/field_probe2_20261103/frame-identities.csv)。[全部 ROI 图](local/field_probe2_20261103/roi-contact.jpg) 的黄色框为图板位置，红色为下方不可用区，紫色为角标位置；每帧变换、角标外框、相关度和留出边界点保存在 geometry 目录。

1944–1946 没有因裁切而直接丢弃。另取标准差低于 4 JPG 码的平坦灰块，只剩每张 13–28 个可用区域；其中节点 16 的有效激励几乎消失，1945 仅一个 B 候选点。它们没有清楚的双节点正向响应，但 A 与未受激的部分 P1 条目仍不能分开。35/50/65% 的可用集合也变化较大，所以保留 unknown，不能把 1946 补成 P2 起始 A。详见 [salvage.json](local/field_probe2_20261103/salvage.json)。

与口述对照，P1 五张和最后八张吻合。1939–1943 则是“P2 页面＋P1 负向条目”的实测组合；它们作为额外负向样本和 A 参照保留，不按双节点正向处理。主定量表的负向用 1935/1936/1937，双节点用最后八张里的六张扰动；1939/1943 也参与就近时间 A 参照。额外负向 1940/1941/1942 单独留在补充结果，尤其不把不同页面当作同条件重复。

## RAW、A 漂移和取样限制

RAW 按 DNG 裁切起点、CFA 相位、12 位打包解码，全部像素重打包断言通过。最终算法再次提取 21 张，逐帧统计文件与第一次修正后的结果字节全同。每种 ROI 都保存 624 行扰动×区域测量，没有主测点因 RAW/JPG 饱和排除。

RAW_WB 是扣黑位的 CFA 均值除以 AsShotNeutral，独立于 JPG 输出曲线。条件输入则由已识别 A 的 JPG 经原模型反演，再按逐块、逐通道 RAW 比例换算到扰动帧；它不是直接读到的 ISP 输入。Y 从 JPG 的 Y 分量解码，Cb/Cr 另存，未把 RGB 转换后所得 Y 充作原生 Y。

| A 配对 | 间隔秒 | RAW 中位变化，R / G / B % | RAW 校正后 Y / Cb / Cr 残差 RMS |
| --- | ---: | --- | --- |
{chr(10).join(drift_table)}

1939–1946 内构图变化明显，不能只用一个整幅曝光倍率。1947–1949 之前没有同一构图下已确认的紧邻 A；主分析在 1943 与 1950 之间逐块插值，并另外用最近一张 A 检查敏感性。1951–1953 则由 1950/1954 夹住。下表的系数包络包含最近 A 与三种 ROI，不能视作统计置信区间。

M 档参数相同不等于逐块输入完全不变。1943→1950 的 RAW 逐块全距为 R {middle['raw_percent_min'][0]:.2f}–{middle['raw_percent_max'][0]:.2f}%、G {middle['raw_percent_min'][1]:.2f}–{middle['raw_percent_max'][1]:.2f}%、B {middle['raw_percent_min'][2]:.2f}–{middle['raw_percent_max'][2]:.2f}%；1950→1954 则为 R {late['raw_percent_min'][0]:.2f}–{late['raw_percent_max'][0]:.2f}%、G {late['raw_percent_min'][1]:.2f}–{late['raw_percent_max'][1]:.2f}%、B {late['raw_percent_min'][2]:.2f}–{late['raw_percent_max'][2]:.2f}%。不能据 RAW 中位数较小就宣称屏幕照度和构图全程稳定。

同一 P2 扰动各两张。下表比较各自减去 A、按 RAW 校正后的效应。选点为至少一张的名义扰动绝对值大于 0.2，表内差异仍含两次输入位置不同的影响。

| 扰动配对 | 成对灰块 n | R / G / B 效应差 RMS | Y / Cb / Cr 效应差 RMS |
| --- | ---: | --- | --- |
{chr(10).join(repeat_table)}

重复性支持两次条目相同；B 的色度差仍大于 R/G。每路只有两帧，不能按灰块数或像素数扩大重复次数。P1 的主页面每种负向只有一帧，无法给出同条件负向重复性。

![漂移与重复性](local/field_probe2_20261103/drift-repeatability.png)

## 输入覆盖与扰动核

以下为首张主扰动在名义峰值两侧、仍位于支持区内的灰点数，以及全部主扰动明显受激灰点的 RAW_WB 范围。明显受激只用名义扰动绝对值大于 0.2 作统计门槛，零点仍参与形状比较。范围端点之间并非连续验收区间。

| 节点 | R 左 / 右点数；RAW_WB 范围 | G 左 / 右点数；RAW_WB 范围 | B 左 / 右点数；RAW_WB 范围 |
| --- | --- | --- | --- |
{chr(10).join(coverage_table)}

三个通道在节点 8、16、19 的两侧都采到了灰点。节点 8 和 19 各有可分辨局部响应，形状也在两次正向扰动中重复出现。RAW 轴的独立自由核复核在 [raw_axis_free_kernels.json](local/field_probe2_20261103/raw_axis_free_kernels.json)。

下面是条件输入轴上自由三角核的诊断拟合。负向先取幅度绝对方向；每组同时拟合背景项。Y 反推除以原 C100 的该通道亮度系数，RGB 投影则用原模型的完整输出方向。这两种反推不一致，表示旧模型不能同时解释观测分量，不能解释成硬件有两个不同的核。

| 通道 / 节点 | Y 反推：峰位 / 半高宽 / 峰幅 | RGB 投影：峰位 / 半高宽 / 峰幅 |
| --- | --- | --- |
{chr(10).join(free_table)}

B 的 Y 权重小，Y 的取整、基线和模型误差会被除法放大。例如负向节点 16 的 Y 半高宽约 64，RGB 投影约 113；不能据此说硬件负向核收窄一半。节点 19 的 B 也出现 Y 峰幅约 4.32、RGB 投影约 1.78 的分歧。表内是输出诊断，不是新的曲线字节单位或应写回的节点位置。三种 ROI、两种核形及全部参数在 [kernel-fits.csv](local/field_probe2_20261103/kernel-fits.csv)。

![扰动核与旧正向](local/field_probe2_20261103/kernel-response.png)

## 负向对称、插值与量化相位

P1 的 R/G/B 负向符号和通道均正确。把旧密集灰阶的节点 16 +2 与新 P1 −2 按同一选点门槛重算，得到以下灰阶 Y 诊断斜率。它是“实测输出／原预测”的局部系数，未把旧组和新组的不同时间、输入分布变成同场正负配对。

| 通道 | 旧 +2 系数 | 新 −2 系数 | 负向 / 正向 |
| --- | ---: | ---: | ---: |
{chr(10).join(symmetry_table)}

R/B 的这项总幅度接近，G 负向约低 13%。这支持符号和大致幅度相反，尚不能宣告严格对称，也不能把 G 的差距直接判成硬件正负不对称。条件输入轴、峰顶采样、屏幕／构图条件和量化相位没有被同场配对消除。额外 P2 页面负向在稀疏灰点上支持同一控制，但 1942 的 B 亮度反推偏差大，不能混入主 P1 表后当作第二次等价重复。

形状比较包括线性三角、平滑余弦、PCHIP 差分、最近节点、左节点保持，以及线性插值后 floor/round。每个固定形状仅拟合一个幅度和背景项。下面列中央 50%、均值输入分支的原生 Y 反推 RMSE，单位为条件曲线码；另有 4×4 空间块均值、RAW 直方图积分及逐帧留出结果。

| 通道 / 节点 | 线性 | PCHIP 差分 | 最近节点 | 线性后 floor | 线性后 round |
| --- | ---: | ---: | ---: | ---: | ---: |
{chr(10).join(shape_table)}

R/G 多处仍支持连续核，PCHIP 与线性的排名会变。B 节点 8 的 Y 分支偏向最近节点，但同一区域的 RGB 投影持续偏向连续核；不能把一个分量的最低残差升级为硬件插值算法。也不能将上一轮节点 16 的形状结论直接推广到所有新节点。

21 张 JPG 的亮度和色度 DC 量化步长均为 1。单个 8×8 块均值对应 0.125 码，还存在 IDCT、像素取整和 ISP 内部量化。floor/round 排名随 ROI、均值／空间块／RAW 直方图分支变化；RAW 直方图包含传感器噪声，不等同于 ISP 降噪后进入曲线的分布。本组不能确定量化相位或舍入顺序。详见 [shape_sensitivity_summary.json](local/field_probe2_20261103/shape_sensitivity_summary.json)。

## Y/Cb/Cr 幅度与彩块

下表分别拟合实测分量变化与原预测的比例；只用明显受激灰点，预测分量绝对值小于 0.08 的点不参与该分量比值。n 为受激灰点总数，各分量的实际 n 另见 [primary-components.json](local/field_probe2_20261103/primary-components.json)。1 表示该局部分量接近原预测。它们不代表 DAT 的 +2／−2 单位改变。

| 通道 / 节点 | Y / Cb / Cr 诊断系数 | Y：ROI 与 A 参照包络 | 灰点 n |
| --- | --- | --- | ---: |
{chr(10).join(component_table)}

节点 8 和 19 不能共用一个全局幅度修正。尤其 B 的灰阶 Y 系数约为 1.94 与 2.28，而 Cb/Cr 并不按同样倍率变化。三种 ROI 与最近 A 都没有消除这个差距。这个结果约束的是原模型的最终输出预测，不能改写成“硬件 B 曲线单位统一翻倍”。

![分量幅度系数](local/field_probe2_20261103/component-response.png)

肤色和 B 色块都被实际激励到。以下列指定通道的条件输入、名义曲线扰动，以及 JPEG 分量差；单位均为 8 位输出码，幅度可因区域均值成为小数。

| 照片 / 条目 / 彩块 | 条件输入 | 名义 Δ曲线 | 实测 ΔY / ΔCb / ΔCr | 原预测 ΔY / ΔCb / ΔCr |
| --- | ---: | ---: | --- | --- |
{chr(10).join(color_table)}

P1 R−2 的肤色 Cb 只有约 +0.026，原模型预测 +0.826；不做 RAW 校正时约 +0.007，缺口不是这一步校正造出来的。P1 B−2 的蓝块 Cr 为约 −0.263，预测却为 +0.140。

P2 B+2 的蓝块 Cr 两次分别约 +0.198、+0.307，预测分别 −0.245、−0.233，方向相反。最近 A 分支仍约 +0.233、+0.290；完全不做 RAW 校正也仍为正。正负方向、两个节点的蓝块都指向原色度导数错误。肤色 R+19 的 Y/Cr 也明显大于预测。单独调整每通道幅度或一个固定 2×2 色度矩阵，不能据此算作通过。

另从 JPG 的 RGB 均值按标准公式独立算 Cb/Cr，不使用 RAW 校正或原前向模型，蓝块的 Cr 正负号仍相同，肤色负向的 Cb 仍接近零。这个复核只检查分量标记和符号，主表继续使用原生 JPG 分量。见 [independent-color-check.json](local/field_probe2_20261103/independent-color-check.json)。

这里不能把灰阶校正无条件移到彩块。例如 B+19 的灰阶 Y 系数约 2.28，蓝块的 Y 比例仅约 1.2–1.4。亮度、色相和分量必须分开标定。完整彩块、三种 ROI 与最近 A 在 [color_sensitivity.json](local/field_probe2_20261103/color_sensitivity.json)，未校正对照在 [color_no_RAW_correction.json](local/field_probe2_20261103/color_no_RAW_correction.json)。

![肤色与 B 色块](local/field_probe2_20261103/color-patches.png)

## 对用户粗测的复核

首五张 P1 现在可识别，顺序与机主口述一致。最后八张的粗测条目也全部得到确认。下表用 1954 作为参考，固定选其 Y=30–80 的 13 个灰区，列 RGB“通道减均值”；这里只用于对照用户的粗测，不用来定量拟合。

| 照片 | 直接 JPG：R / G / B | 按 RAW 校正后：R / G / B |
| --- | --- | --- |
{chr(10).join(low_table)}

1949 的 R 直接特征约 0.833，1951 约 0.946；按 RAW 校正后约 0.830 与 0.860。1949 不是未受激 A。中间亮度的漂移要与实际节点支持区、输入位置变化和量化分开看，不能把“通道减均值”的幅度直接当曲线码距。

## 给 recipe-redo-r1 的结论

1. MOUNT L1 可以继续生成候选。三路命名、节点 16 负向和节点 8/19 双正向控制成立；两个分离响应带和两次正向重复都观测到了。不要改节点编号或字节上的 ±2 扰动规格。
2. 没有通过全颜色定量验收的连续亮度范围。上表扩大的是局部已采灰点：节点 8、16、19 分别有独立 RAW_WB 支持；不把区间空档、未测节点或其它色相算作已验收。给配方评分时仍要保留模型误差。
3. 分段线性可继续作为工作模型，另保留平滑、输入分布和量化分支。不能把自由峰位写回硬件节点，也不能据 B 的单个 Y 分支改成最近节点。
4. 输出模型应分别标定 Y/Cb/Cr 随输入亮度、色相和扰动方向变化的局部导数。表内系数可用于本轮条件下的敏感性评估，不能作为统一通道增益；B 灰阶与蓝块的 Y 差异以及蓝块 Cr 反号是必须保留的反例。
5. 节点 16 正负仍缺同场配对。G 的方向差距和 B 弱 Y 分量不能被一个幅度常数吸收，量化相位也未定。此次不改前向模型源码、配方、DAT 或机身。机器可读交接为 [recipe_redo_handoff.json](local/field_probe2_20261103/recipe_redo_handoff.json)。

## 是否需要重拍

为了确认条目、符号与两个新节点的局部响应，不必补拍。P1 原五张和最后八张已经覆盖所需扰动；三个 unknown 保留即可，不需要为了还原它们的菜单顺序重拍整组。

若下一道门槛要求“节点 16 定量正负对称”，最少再拍 8 张：同一 P1 灰阶页、同一曝光，A→R+2→R−2→G+2→G−2→B+2→B−2→A。必须先准备同时含节点 16 正负条目的测试 DAT；现 probe2 的 P2 +2 改的是 8/19，不能代替这里的 +16。固定支撑，四角和三个彩块完整入镜，避免本次下方裁切。

若还要检验输入量化相位，再用屏幕灰码统一微移 1 码的第二相位重复这 8 张，共 16 张。两相位要各自用 A 的 RAW 核实输入确有变化。它能约束相位依赖，仍不能单凭照片给 ISP 舍入步骤命名；唯一确定 floor/round 还需要静态舍入路径证据。这是后续定标采样，不是替这 21 张补身份。P2 无需再拍一整套相同的 8 张。

## 文件、哈希与清理

脚本为 [probe2_field.py](probe2_field.py) 与 [probe2_field_report.py](probe2_field_report.py)。复现时用现有 `studio/.venv/bin/python -I -B`、nice 15，数字库线程固定 1；最多两个互不依赖的计算作业。按 inventory、geometry、extract、identify、classify、measure、fit、fit_primary、diagnostics、salvage、refine 的顺序执行分析阶段。`extract_verify` 再次提取并核对全部帧字节；报告脚本的 figures、tables、independent、validate、cleanup、report、seal 依次生成交付物。重跑时要再次清理指定 Scratch，不要启动 Studio。

输入 manifest SHA-256：`{input_digest}`。附 [FIELD_PROBE2.SHA256SUMS](FIELD_PROBE2.SHA256SUMS) 和 [local/SHA256SUMS](local/field_probe2_20261103/SHA256SUMS)，覆盖报告、脚本、全部 21 帧统计、图表与回执。主测 624 行见 [main-points.csv](local/field_probe2_20261103/main-points.csv)，输入和验证在 [acceptance.json](local/field_probe2_20261103/acceptance.json)。

原照片、封存的旧报告、页面和探针包均未改。没有访问卡或相机，也未启动 Studio、联网、改配方或做 Git 写操作。`{TMP}` 已删除，无本任务计算进程残留，清理回执为 [cleanup.json](local/field_probe2_20261103/cleanup.json)。
'''
    (HERE/'FIELD_PROBE2.md').write_text(text)
    print(json.dumps(dict(status='PASS',report='FIELD_PROBE2.md',verdict='部分可用',identified=18,unknown=3),ensure_ascii=False))


def cleanup():
    assert TMP==Path('/Volumes/Workspace/Scratch/tmp/projectricoh/probe2-field-20261103') and not TMP.is_symlink()
    own={os.getpid(),os.getppid()};active=[]
    for line in subprocess.check_output(['/bin/ps','-axo','pid=,ppid=,command='],text=True).splitlines():
        pid,ppid,command=line.strip().split(None,2)
        if int(pid) in own:continue
        if str(TMP) in command or ('probe2_field' in command and 'python' in command):active.append(int(pid))
    assert not active,active
    files=[p for p in TMP.rglob('*') if p.is_file()] if TMP.exists() else []
    total=sum(p.stat().st_size for p in files)
    if TMP.exists():shutil.rmtree(TMP)
    assert not TMP.exists()
    dump('cleanup.json',dict(status='PASS',temporary_directory=str(TMP),files=len(files),bytes=total,temporary_directory_absent=True,
        active_compute_processes=active,card_camera_or_Studio_access=False))
    print(json.dumps(dict(status='PASS',files=len(files),bytes=total,temporary_directory_absent=True)))


def seal():
    assert not TMP.exists()
    local=OUT/'SHA256SUMS';files=[p for p in OUT.rglob('*') if p.is_file() and p!=local]
    local.write_text(''.join(sha(p)+'  '+str(p.relative_to(ROOT))+'\n' for p in sorted(files)))
    public=HERE/'FIELD_PROBE2.SHA256SUMS';files=[HERE/'FIELD_PROBE2.md',HERE/'probe2_field.py',HERE/'probe2_field_report.py',local]
    public.write_text(''.join(sha(p)+'  '+str(p.relative_to(ROOT))+'\n' for p in files))
    verify()


def verify():
    assert not TMP.exists();counts={}
    for sums in (HERE/'FIELD_PROBE2.SHA256SUMS',OUT/'SHA256SUMS'):
        count=0
        for line in sums.read_text().splitlines():
            wanted,name=line.split('  ',1);assert sha(ROOT/name)==wanted,name;count+=1
        counts[str(sums.relative_to(ROOT))]=count
    print(json.dumps(dict(status='PASS',verified=counts,temporary_directory_absent=True)))


def main():
    p=argparse.ArgumentParser();p.add_argument('stage',choices=['figures','tables','independent','validate','cleanup','report','seal','verify']);args=p.parse_args()
    assert os.getpriority(os.PRIO_PROCESS,0)>=15
    vol=plistlib.loads(subprocess.check_output(['/usr/sbin/diskutil','info','-plist','/Volumes/Workspace']))
    assert vol['VolumeUUID']=='14BE04EB-AF49-497E-B36A-B078B2F7C5E8' and vol['FilesystemType']=='apfs' and vol['WritableVolume']
    globals()[args.stage]()


if __name__=='__main__':main()
