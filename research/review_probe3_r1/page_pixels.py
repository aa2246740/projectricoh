"""Check screenshot samples, marker decoding and invariance across all eight steps."""
import hashlib
import json
import os
from pathlib import Path

for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','VECLIB_MAXIMUM_THREADS'):
    os.environ[key]='1'
import numpy as np
from PIL import Image
from scipy.ndimage import find_objects, label

HERE=Path(__file__).resolve().parent
OUT=HERE/'local/page'


def bounds(rect,dpr):
    return tuple(int(v) for v in (np.ceil(rect['x']*dpr),np.ceil(rect['y']*dpr),
        (rect['x']+rect['w'])*dpr,(rect['y']+rect['h'])*dpr))


def marker_bits(image,rect):
    x,y,w,h=rect
    cells=np.array([[image[int(y+(r+.5)*h/9),int(x+(c+.5)*w/9)]
        for c in range(9)] for r in range(9)])
    return np.min(cells,axis=-1)>=220


def main():
    summary=json.loads((OUT/'check.json').read_text())
    digest=hashlib.sha256((HERE.parent/'probe_pack_r3/ramp3.html').read_bytes()).hexdigest()
    assert summary['status']=='PASS' and summary['htmlSha256']==digest
    layout=json.loads((OUT/'layout.json').read_text());candidates=[]
    for marker in layout['markers']:
        matrix=np.zeros((9,9),bool);matrix[[0,-1],:]=True;matrix[:,[0,-1]]=True
        matrix[2:7,2:7]=np.array([[b=='1' for b in row] for row in marker['bits']])
        candidates.extend((marker['corner'],r,np.rot90(matrix,r)) for r in range(4))
    hamming=min(int(np.sum(a[2]!=b[2])) for i,a in enumerate(candidates) for b in candidates[i+1:])
    assert hamming>=4
    receipts=[];first={};light={}
    for case in summary['cases']:
        name=case['name'];data=json.loads((OUT/(name+'.json')).read_text());dpr=data['dpr']
        pixels=np.array(Image.open(OUT/(name+'.png')).convert('RGB'))
        for patch in data['patches']:
            x1,y1,x2,y2=bounds(patch['sample'],dpr)
            roi=pixels[y1:y2,x1:x2].astype(int)
            wanted=np.array([int(x) for x in patch['rgb'].split(',')])
            assert roi.size and np.max(abs(roi-wanted))==0,(name,patch['id'])
        components,count=label(np.min(pixels,axis=-1)>245);found=[]
        for component in find_objects(components):
            yy,xx=component;w,h=xx.stop-xx.start,yy.stop-yy.start
            if min(w,h)<14 or abs(w-h)>2:continue
            bits=marker_bits(pixels,(xx.start,yy.start,w,h))
            matches=sorted((int(np.sum(bits!=b)),corner,r) for corner,r,b in candidates)
            distance,corner,rotation=matches[0]
            if distance>2 or matches[1][0]-distance<3:continue
            found.append(dict(corner=corner,rotation=rotation,bit_errors=distance,bbox=[xx.start,yy.start,w,h]))
        assert len(found)==4 and {m['corner'] for m in found}=={'TL','TR','BL','BR'},(name,found)
        for marker in found:
            box=next(m['box'] for m in data['markers'] if m['corner']==marker['corner'])
            assert abs(marker['bbox'][0]-box['x']*dpr)<2
            assert abs(marker['bbox'][1]-box['y']*dpr)<2
        x1,y1,x2,y2=bounds(data['frame'],dpr);frame=pixels[y1:y2,x1:x2].copy()
        total=np.sum(frame,axis=(0,1),dtype=np.int64).tolist()
        lx1,ly1,lx2,ly2=bounds(data['label'],dpr)
        frame[ly1-y1:ly2-y1,lx1-x1:lx2-x1]=0
        key=case['caseName']
        if key not in first:first[key]=frame;light[key]=total
        assert np.array_equal(frame,first[key]),(name,'pixels outside fixed label changed')
        assert total==light[key],(name,'total framed RGB changed')
        receipts.append(dict(case=name,uniform_samples=52,located_markers=found,
            frame_sum_RGB=total,all_pixels_outside_label_unchanged=True))
    result=dict(status='PASS',htmlSha256=digest,cases=receipts,
        marker_minimum_hamming_distance=hamming,viewport_groups=len(first),
        label_only_changes=True,frame_total_RGB_constant=True,
        measured_surroundings_pixel_identical=True,
        limitation='Rendered pixels only. Physical screen local dimming, flare, blur and moire remain field conditions.')
    (HERE/'local/pixels.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(status='PASS',cases=len(receipts),sample_regions=52*len(receipts),
        marker_decodes=4*len(receipts),constant_light_groups=len(first))))


if __name__=='__main__':main()
