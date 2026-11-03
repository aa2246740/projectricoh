"""Run the actual Studio photograph path against isolated LUT data."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from support import setup,ROOT,HERE,DATA,SCRATCH,digest,dump
setup()
import hashlib
import numpy as np
from PIL import Image,ImageDraw,ImageOps,ImageFont
from data import creator_jobs,selected_paths,scene,Cube,Target,camera_model,stats,de
from gxr_studio.render.service import RenderService
from gxr_studio.render.params import EditState,EditError
from gxr_studio.lut.photo import color_image

class ReadLibrary:
    root=ROOT/'captures'
    def abspath(self,path):
        p=(ROOT/path).resolve()
        if not p.is_relative_to(self.root):
            raise ValueError('Photo outside captures')
        return p

def jpeg_of(path):
    p=ROOT/path
    for ext in ('.JPG','.jpg','.JPEG','.jpeg'):
        q=p.with_suffix(ext)
        if q.is_file(): return q
    raise FileNotFoundError('No paired JPEG for '+path)

def main():
    lib=ReadLibrary()
    render=RenderService(SCRATCH/'photo-path',lib,proxy_bytes=8<<20,result_bytes=8<<20,max_concurrent=1)
    paths=[selected_paths()[0],selected_paths()[15]]
    rows=[]
    sheet=Image.new('RGB',(320*5,260*4+40),'#161a20')
    draw=ImageDraw.Draw(sheet)
    font=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf',16)
    draw.text((10,10),'GXR photos | JPEG display input / scene V-Log hypothesis | computer prediction',font=font,fill='white')
    model,dat,_=camera_model()
    for pi,path in enumerate(paths):
        arrays,meta=scene(path)
        jp=jpeg_of(path)
        shot={'id':f'eval-{pi}','lens':meta['unique_model'],'iso':meta['iso'],
              'files':{'dng':{'relpath':path},'jpg':{'relpath':str(jp.relative_to(ROOT))}}}
        with Image.open(jp) as im:
            shown=ImageOps.exif_transpose(im).convert('RGB')
            shown.thumbnail((320,210))
            sheet.paste(shown,(0,40+pi*520+30))
        draw.text((8,40+pi*520),meta['unit']+' original JPEG',font=font,fill='white')
        for ji,job in enumerate(creator_jobs()):
            item=render.luts.add(job['path'].read_bytes(),job['path'].name)
            render.luts.patch(item['cube_id'],{'input_space':'srgb','output_space':'srgb'})
            image,_,labels=color_image(render,lib,shot,EditState(lut=item['cube_id']),max_edge=320,quality=90,base='auto',full=False)
            x=(ji+1)*320;y=40+pi*520
            sheet.paste(Image.fromarray(image),(x,y+30))
            ascii_name={'千禧回声 A':'QianXi A','千禧回声 B':'QianXi B'}.get(job['name'],job['name'])
            draw.text((x+6,y),ascii_name+' sRGB JPEG',font=font,fill='white')
            cube=Cube.read(job['path'])
            log=Target(cube,'vlog','srgb').render(np.zeros_like(arrays['codes']),arrays['xyz'])
            h,w=arrays['shape']
            li=Image.fromarray(np.uint8(np.rint(np.clip(log,0,255))).reshape(int(h),int(w),3))
            li=li.resize((image.shape[1],image.shape[0]),Image.Resampling.LANCZOS)
            sheet.paste(li,(x,y+290))
            draw.text((x+6,y+260),'V-Log hypothesis',font=font,fill='white')
            rows.append({'name':job['name'],'photo':path,'jpeg':str(jp.relative_to(ROOT)),
                         'jpeg_sha256':digest(jp),'unit':meta['unit'],'studio_photo_path':'PASS',
                         'shape':list(image.shape),'render_sha256':hashlib.sha256(image.tobytes()).hexdigest(),
                         'labels':labels,'input':'srgb','output':'srgb'})
    # Exercise the full log branch using the actual half-resolution RAW reader.
    for pi,path in enumerate(paths):
        _,meta=scene(path)
        shot={'id':f'raw-{pi}','lens':meta['unique_model'],'iso':meta['iso'],'files':{'dng':{'relpath':path}}}
        cube=DATA/'Luts/Hasselblad/Hasselblad_Standard_Phocus_X2D_VLog_sRGB_65.cube'
        item=render.luts.add(cube.read_bytes(),cube.name)
        render.luts.patch(item['cube_id'],{'input_space':'vlog','output_space':'srgb'})
        try:
            image,_,labels=color_image(render,lib,shot,EditState(lut=item['cube_id']),max_edge=320,quality=90,base='auto',full=False)
            row={'case':'actual log RAW path','photo':path,'unit':meta['unit'],'result':'PASS',
                 'shape':list(image.shape),'labels':labels,'sha256':hashlib.sha256(image.tobytes()).hexdigest()}
        except EditError as e:
            row={'case':'actual log RAW path','photo':path,'unit':meta['unit'],
                 'result':'REFUSED','error_code':e.code,'message':e.message}
        rows.append(row)
    sheet.save(HERE/'creator_input_contactsheet.jpg',quality=92)
    dump('studio_photo_checks.json',rows)
    print('Photo path checks',len(rows),flush=True)

if __name__=='__main__':
    main()
