"""Drive normal import/edit/export APIs and verify the actual HDR outputs."""
import io
import json
import math
import sys
import time
from pathlib import Path

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[1]
TMP=Path('/Volumes/Workspace/Scratch/tmp/projectricoh/review-studio-hdr')/'edits'
TMP.mkdir(exist_ok=True)
sys.path[:0]=[str(OUT),str(ROOT/'studio/src'),str(ROOT/'studio/tests')]
import numpy as np
from PIL import Image
from fastapi.testclient import TestClient
from scipy import ndimage
import hdr_support as hs
from format_oracle import inspect,stops,digest
from gxr_studio import audit
from gxr_studio.app import create_app
from gxr_studio.config import Settings
from gxr_studio.finish.compose import finish_array
from gxr_studio.finish.hdr_export import HdrTrack
from gxr_studio.finish.spec import Geometry,parse_frame,parse_stamp
from gxr_studio.hdr import derived
from gxr_studio.render.params import EditState
from support.fake_card import make_fake_card

audit.forbid_volumes()
audit.forbid_network(True)
rows=[]
def emit(row):
    rows.append(row)
    with (OUT/'edit_cases.jsonl').open('a') as f:
        f.write(json.dumps(row,ensure_ascii=False)+'\n')
    print(json.dumps(row,ensure_ascii=False),flush=True)

def reference_geometry():
    h,w=180,280
    yy,xx=np.mgrid[0:h,0:w].astype(np.float32)
    layer=0.15+0.2*xx/(w-1)+0.5*yy/(h-1)
    rgb=np.repeat(np.floor(layer[...,None]*255+0.5).astype(np.uint8),3,axis=2)
    rect=(0.12,0.10,0.73,0.75)
    for angle,turns,flip in [(3.25,1,False),(-4.1,3,True),(7.4,2,False)]:
        geom=Geometry(straighten=angle,rotate90=turns,flip=flip)
        track=HdrTrack(None)
        track.layer=np.dstack([layer,np.zeros_like(layer)])
        frame=parse_frame({'style':'gallery','color':'white','weight':'thick'})
        spec=parse_stamp({'enabled':False})
        output,_=finish_array(rgb,EditState(geometry=geom),stage='final',frame=frame,stamp=spec,crop_rect=rect,
                              meta={},taken=None,file_time=None,from_raw=False,track=track)
        ref=Image.fromarray(layer).rotate(-angle,resample=Image.Resampling.BILINEAR,expand=False)
        for _ in range(turns):
            ref=ref.transpose(Image.Transpose.ROTATE_90)
        if flip:
            ref=ref.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        x,y,bw,bh=[math.floor(v*s+0.5) for v,s in zip(rect,(ref.width,ref.height,ref.width,ref.height))]
        ref=np.asarray(ref)[y:y+bh,x:x+bw]
        margin=max(8,round(max(ref.shape)*0.07))
        expected=np.full((ref.shape[0]+2*margin,ref.shape[1]+2*margin),np.nan,np.float32)
        expected[margin:margin+ref.shape[0],margin:margin+ref.shape[1]]=ref
        actual=track.layer[...,0]
        assert actual.shape==expected.shape==output.shape[:2]
        assert np.array_equal(np.isfinite(actual),np.isfinite(expected))
        err=float(np.nanmax(np.abs(actual-expected)))
        assert err<1e-5,err
        emit({'kind':'independent_geometry','angle':angle,'turns':turns,'flip':flip,'max_raw_luma_difference':err,'photo_mask_equal':True})

reference_geometry()
volumes=TMP/'volumes'
card=make_fake_card(volumes,pairs=0,jpg_only=0)
folder=card.root/'DCIM/100RICOH'
for orientation in [1,6,7]:
    jpg,dng=hs.pair(0,orientation)
    (folder/f'ORIENT{orientation}.JPG').write_bytes(jpg)
    (folder/f'ORIENT{orientation}.DNG').write_bytes(dng)
first=hs.scene(seed=0)
second=first.copy()
first[96:136,420:460]=0.035
second[96:136,500:540]=0.035
(folder/'MOTION.JPG').write_bytes(hs.camera_jpeg(second))
(folder/'MOTION.DNG').write_bytes(hs.camera_dng(first))
before={p.name:digest(p.read_bytes()) for p in folder.iterdir()}
settings=Settings(library_dir=TMP/'library',home_dir=TMP/'app-home',export_dir=TMP/'exports',volumes_roots=(volumes,),
                  token='review-local-token',port=8765,min_free_bytes=0,web_dir=ROOT/'studio/web')

def wait(client,job_id):
    end=time.monotonic()+600
    while time.monotonic()<end:
        job=client.get('/api/jobs/'+job_id).json()
        if not job['running']:
            return job
        time.sleep(0.01)
    raise AssertionError('job did not finish')

def export(client,photo,hdr=False,edge=None):
    r=client.post('/api/photos/'+photo['id']+'/export',json={'quality':92,'hdr':hdr,'long_edge':edge})
    assert r.status_code==200,r.text
    info=r.json()
    return info,Path(info['path']).read_bytes()

with TestClient(create_app(settings),base_url='http://127.0.0.1:8765',headers={'X-GXR-Token':settings.token}) as client:
    cards=client.get('/api/cards').json()
    assert len(cards)==1
    start=client.post('/api/import',json={'card_id':cards[0]['id']})
    assert start.status_code==202,start.text
    job=wait(client,start.json()['id'])
    hdr_jobs=[j for j in client.get('/api/jobs').json() if j['kind']=='hdr']
    assert len(hdr_jobs)==1
    hdr_job=wait(client,hdr_jobs[0]['id'])
    assert job['error'] is None and job['progress']['state']=='done'
    assert hdr_job['error'] is None
    photos={p['name']:p for p in client.get('/api/photos').json()}
    lib=client.app.state.ctx.lib
    for name,photo in photos.items():
        shot=lib.get_shot(photo['id'])
        for kind in ['jpg','dng']:
            assert digest(lib.abspath(shot['files'][kind]['relpath']).read_bytes())==shot['files'][kind]['sha256']
        derived_path=derived.hdr_path(lib,photo['id'])
        if derived_path.exists():
            original=lib.abspath(shot['files']['jpg']['relpath']).read_bytes()
            fmt,_,_=inspect(original,derived_path.read_bytes())
            emit({'kind':'actual_import_derived','case':name,'status':photo['hdr'],'format':fmt})
    motion=photos['MOTION']
    motion_info,_=export(client,motion,True)
    emit({'kind':'local_motion_api','case':'object_40_move_80','import_status':motion['hdr'],
          'export_hdr':motion_info['hdr'],'export_note':motion_info['hdr_note'],
          'import_message':job['progress']['message'],'job_failed':hdr_job['progress']['failed']})
    for orientation in [1,6,7]:
        photo=photos['ORIENT'+str(orientation)]
        for geom,rect,case in [({},None,'plain'),({'rotate90':1,'straighten':2.3,'flip':True},[0.1,0.1,0.75,0.7],'geometry')]:
            assert client.delete('/api/photos/'+photo['id']+'/edit').status_code==200
            assert client.delete('/api/photos/'+photo['id']+'/crop').status_code==200
            if geom:
                r=client.put('/api/photos/'+photo['id']+'/edit',json={'geometry':geom})
                assert r.status_code==200,r.text
            if rect:
                r=client.put('/api/photos/'+photo['id']+'/crop',json={'preset':'free','rect':rect})
                assert r.status_code==200,r.text
            for edge in [None,256]:
                _,sdr=export(client,photo,False,edge)
                info,hdr=export(client,photo,True,edge)
                assert info['hdr'] is True,info
                fmt,_,_=inspect(sdr,hdr)
                assert Image.open(io.BytesIO(hdr)).getexif().get(274)==1
                emit({'kind':'actual_export','case':case,'orientation':orientation,'edge':edge,'format':fmt})
    photo=photos['ORIENT1']
    for i,style in enumerate(['gallery','leica','hasselblad','film','instant','canvas']):
        assert client.delete('/api/photos/'+photo['id']+'/edit').status_code==200
        assert client.delete('/api/photos/'+photo['id']+'/crop').status_code==200
        r=client.put('/api/photos/'+photo['id']+'/edit',json={'frame':{'style':style,'color':'white','weight':'thick','text':'2026'},
                         'stamp':{'enabled':True,'date_override':'2026-10-31','corner':['tr','tl','br','bl'][i%4],
                                  'size':'large','glow':bool(i%2),'color':'orange'}})
        assert r.status_code==200,r.text
        _,sdr=export(client,photo)
        info,hdr=export(client,photo,True)
        assert info['hdr'] is True,info
        fmt,codes,_=inspect(sdr,hdr)
        lg=stops(codes,fmt['iso_values'])
        sdr_rgb=np.asarray(Image.open(io.BytesIO(sdr)).convert('RGB')).astype(np.int16)
        stamp_pixels=(sdr_rgb[...,0]>180)&(sdr_rgb[...,1]>30)&(sdr_rgb[...,1]<190)&(sdr_rgb[...,2]<100)
        ys,xs=np.nonzero(stamp_pixels)
        assert ys.size>10,(style,int(ys.size))
        stamp_values=lg[ys//4,xs//4]
        assert float(stamp_values.max())<0.1,(style,float(stamp_values.max()))
        assert float(stamp_values.mean())<0.01,(style,float(stamp_values.mean()))
        strips=np.concatenate([lg[:2].ravel(),lg[-2:].ravel(),lg[:,:2].ravel(),lg[:,-2:].ravel()])
        # Bottom-only and fitted canvases need the corresponding actual border.
        if style=='leica':
            strips=lg[-10:].ravel()
        elif style=='canvas':
            strips=np.concatenate([lg[:10].ravel(),lg[-10:].ravel()])
        assert float(strips.max())<0.1,(style,float(strips.max()))
        assert float(strips.mean())<0.01,(style,float(strips.mean()))
        emit({'kind':'border_and_stamp','style':style,'edge_gain_max_stops':float(strips.max()),
              'edge_gain_mean_stops':float(strips.mean()),'stamp_pixels':int(ys.size),
              'stamp_gain_max_stops':float(stamp_values.max()),'stamp_gain_mean_stops':float(stamp_values.mean()),'format':fmt})
    for adjust,curve in [({'exposure_ev':0.7},None),({'exposure_ev':-0.5},{'master':[[0,0],[64,55],[128,145],[192,205],[255,255]]})]:
        assert client.delete('/api/photos/'+photo['id']+'/edit').status_code==200
        r=client.put('/api/photos/'+photo['id']+'/edit',json={'adjust':adjust,'curve':curve})
        assert r.status_code==200,r.text
        _,sdr=export(client,photo)
        info,hdr=export(client,photo,True)
        assert info['hdr'] is True,info
        fmt,_,_=inspect(sdr,hdr)
        emit({'kind':'exposure_curve','adjust':adjust,'curve':curve,'format':fmt})

assert {p.name:digest(p.read_bytes()) for p in folder.iterdir()}==before
assert audit.network_attempts()==[]
(OUT/'edit_summary.json').write_text(json.dumps({'cases':len(rows),'card_original_hashes_equal':True,
                                              'local_motion_api':[r for r in rows if r['kind']=='local_motion_api']},indent=2,ensure_ascii=False)+'\n')
print(json.dumps({'cases':len(rows),'card_original_hashes_equal':True}))
