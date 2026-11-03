"""GR IV studio chart, plus the two studios' standardized Kodak gray scales."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import common as c
from common import np
from raw_io import RawDng,dng_module
from extract import sample,GXR,PREVIEW,NAMES
from PIL import Image,ImageDraw
import datetime
import json

GRIV='artifacts/downloads/dpreview-gr4-studio/gr4_studio_daylight_iso100.dng'
GRIV_PREVIEW='artifacts/downloads/dpreview-gr4-studio-preview/gr4_studio_preview.jpg'
GRIV_SHA='2e438c7e9945591ed2a897a6a4df40da23adf0cb45b89b1a7a1ab7f2d6a967c4'


def extract_chart(raw_path,preview_path,corners=None,prefix='griv'):
    d=RawDng(c.inp(raw_path));im=Image.open(c.inp(preview_path)).convert('RGB')
    overlay=im.copy();draw=ImageDraw.Draw(overlay);rows=[]
    if corners is None: corners=[[650,137],[949,137],[949,331],[650,331]]
    # Projective coordinates include the patch grid, excluding the outer black frame.
    m=[];z=[]
    for (u,v),(x,y) in zip([(0,0),(6,0),(6,4),(0,4)],corners):
        m.extend([[u,v,1,0,0,0,-u*x,-v*x],[0,0,0,u,v,1,-u*y,-v*y]]);z.extend([x,y])
    h=np.r_[np.linalg.solve(m,z),1].reshape(3,3)
    for row in range(4):
        for col in range(6):
            index=row*6+col;centre=h@np.array([col+.5,row+.5,1]);centre=centre[:2]/centre[2]
            p1=h@np.array([col+.27,row+.27,1]);p1=p1[:2]/p1[2]
            p2=h@np.array([col+.73,row+.73,1]);p2=p2[:2]/p2[2]
            roi=[float(p1[0]),float(p1[1]),float(p2[0]),float(p2[1])]
            record=dict(chart='ColorChecker',id=str(index+1),index=index,name=NAMES[index],
                        nominal_preview_xy=centre,roi_preview=roi,status='primary',reason='clear centre')
            record.update(sample(d,roi,im.size));flags=[]
            if max(record['saturation_fraction'])>0: flags.append('raw-saturation')
            if min(record['raw_mean'])<.0003:flags.append('very-low-signal')
            if max(record['quadrant_relative_range'])>.12:flags.append('spatial-gradient-or-contamination')
            record.update(usable=not flags,quality_flags=flags,
                          glare_status='no clipping; veil not separable from material/lighting using one photograph')
            rows.append(record);draw.rectangle(roi,outline='#44dd55' if record['usable'] else '#ff5533',width=1)
    overlay.save(c.LOCAL/f'patch_map_{prefix}.png');c.dump(f'patches_{prefix}.json',rows)
    neutrals=[r for r in rows if r['usable'] and r['index']>=18]
    ratios=np.array([np.array(r['raw_trimmed'])/r['raw_trimmed'][1] for r in neutrals])
    n=np.median(ratios,axis=0);col=dng_module().DngColour(d);xy,it,converged=col.neutral_to_xy(n)
    result=dict(metadata=d.summary(),usable=sum(r['usable'] for r in rows),
          neutral_patch_ids=[r['id'] for r in neutrals],neutral_camera_rgb_green1=n,
          matrix_conditioned_white=col.white_info(xy,n,it,converged),corners_preview=corners,
          source='real public studio RAW, original CFA samples; not synthetic volunteer data',
          spectral_reference='post-Nov2014 DCamProf reference as model, with old-formulation stress run',
          flat_field_measured=False)
    c.dump(f'extraction_{prefix}.json',result)
    print(prefix,'usable',result['usable'],'CCT',round(float(result['matrix_conditioned_white']['cct_K'])))
    return d


def gray_scales():
    all_rows=[]
    for camera,raw,preview,left,right,top,bottom,exclude in [
        ('gxr',GXR,PREVIEW,306,1298,122,202,[4,5,6]),
        ('griv',GRIV,GRIV_PREVIEW,610,988,82,115,[])]:
        d=RawDng(c.inp(raw));im=Image.open(c.inp(preview)).convert('RGB');draw=ImageDraw.Draw(im)
        for i in range(20):
            x=left+(i+.5)*(right-left)/20;y=(top+bottom)/2
            roi=[x-(right-left)/20*.22,y-(bottom-top)*.22,x+(right-left)/20*.22,y+(bottom-top)*.22]
            r=dict(camera=camera,step=i,roi_preview=roi,usable=False)
            if i in exclude:r['reason']='globe occlusion'
            else:
                r.update(sample(d,roi,im.size));r['usable']=max(r['saturation_fraction'])==0 and min(r['raw_mean'])>.0003
                r['reason']='candidate neutral; reflectance and local illumination not independently known'
                draw.rectangle(roi,outline='#44dd55' if r['usable'] else '#ff5533',width=1)
            all_rows.append(r)
        im.save(c.LOCAL/f'kodak_gray_map_{camera}.png')
    result=[]
    for camera in ('gxr','griv'):
        rows=[r for r in all_rows if r['camera']==camera and r['usable']]
        a=np.array([r['raw_trimmed'] for r in rows]);ratio=a/a[:,1,None]
        result.append(dict(camera=camera,usable_steps=[r['step'] for r in rows],
                     ratio_chromaticity_spread=np.std(ratio,axis=0),
                     raw_r_over_g_range=[float(min(ratio[:,0])),float(max(ratio[:,0]))],
                     raw_b_over_g_range=[float(min(ratio[:,2])),float(max(ratio[:,2]))]))
    c.dump('kodak_gray.json',dict(rows=all_rows,summary=result,
         shared_object_type=True,same_physical_strip=False,measured_spectral_reference=False,
         contribution='neutral-axis and flare/field diagnostics, not independent colored spectral constraints',
         cannot_disentangle='strip aging, spectral neutrality, illumination gradient, lens veil and residual black'))


def main():
    p=c.inp(GRIV);assert c.sha(p)==GRIV_SHA and p.stat().st_size==35265434
    c.inp('artifacts/downloads/dpreview-gr4-studio/SOURCE.txt')
    extract_chart(GRIV,GRIV_PREVIEW);gray_scales()
    records=c.read(c.LOCAL/'sources.json')
    if not any(r['label']=='dpreview-griv-orchestrator' for r in records):
        records.append(dict(label='dpreview-griv-orchestrator',
          url='https://www.dpreview.com/wp-content/uploads/image-compare/519596/539993/3af632058d5646a793ebb81bfd145c78.dng',
          date_utc=datetime.datetime.fromtimestamp(p.stat().st_mtime,datetime.timezone.utc).isoformat(),
          file=GRIV,sha256=GRIV_SHA,bytes=p.stat().st_size,status=200,method='GET',untrusted=True,
          downloaded_by='orchestrator native T3 browser; not downloaded again by this worker'))
        c.dump('sources.json',records)


if __name__=='__main__':main()
