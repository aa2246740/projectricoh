"""Labelled computer predictions and adjacent display-code measurements."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import support as s
s.dependencies()
import csv
import json
import hashlib
import time
import numpy as np
from PIL import Image,ImageDraw,ImageFont,PngImagePlugin
import knobs as k
from bridge import C
from checks import level_request
from model_adapter import Model,masks

DISPLAY=(-9,-5,-2,0,2,5,9)
AMOUNT=(0,30,70,100,120,140,150)
NAMES={'amount':'强度','contrast':'对比','highlight':'高光','shadow':'阴影','fade':'褪黑',
       'saturation':'饱和','warmth':'冷暖','tint':'品绿','split':'分离色调','filter':'黑白滤镜','tone':'黑白色调'}
FONT=Path('/System/Library/Fonts/Supplemental/Songti.ttc')


def stats(a):
    if not len(a):return dict(n=0,median=None,mean=None,p90=None,fraction_ge_1=None)
    return dict(n=len(a),median=float(np.median(a)),mean=float(a.mean()),p90=float(np.percentile(a,90)),fraction_ge_1=float((a>=1).mean()))


def main():
    s.guard();s.verify_inputs();modules={m['name']:m for m in s.parse()};c=C(build=False);model=Model()
    cal=json.loads((s.LOCAL/'calibration.json').read_text());main_groups=cal['groups']
    alternatives=json.loads((s.LOCAL/'alternatives.json').read_text())
    scenes=json.loads((s.LOCAL/'scenes.json').read_text());inputs={};samples={}
    for scene in scenes:
        with np.load(s.LOCAL/(scene['id']+'_input.npz'),allow_pickle=False) as z:x=z['x'].copy();size=tuple(z['size'])
        inputs[scene['id']]=(x,size)
        # Fixed 64 x 43 lattice. Each point is a CFA area mean from the 196px input.
        image=x.reshape(size[1],size[0],3)
        yy=np.linspace(0,size[1]-1,43).round().astype(int);xx=np.linspace(0,size[0]-1,64).round().astype(int)
        samples[scene['id']]=image[yy[:,None],xx[None,:]].reshape(-1,3)
    folder=s.LOCAL/'previews';folder.mkdir(exist_ok=True)
    f_title=ImageFont.truetype(str(FONT),24);f_text=ImageFont.truetype(str(FONT),17)
    records=[];metric_rows=[];index=[];start=time.monotonic()
    directions=[]
    for group_num,g in enumerate(main_groups+alternatives):
        unit,slot,param=g['unit'],g['slot'],g['param'];base=modules[unit]['entries'][slot];stock=modules[unit]['entries'][4]
        alt=group_num>=len(main_groups);method='T1' if g.get('wb_method',0) else 'offset' if g.get('tone_method',0) else 'rowsum'
        name=f'{unit}-{slot:02d}-{param}'+(f'-alternative-{method}' if alt else '')+'.png'
        levels=AMOUNT if param=='amount' else DISPLAY
        width,height=196,130;sheet=Image.new('RGB',(width*7,(height+38)*4+100),'#f4f2ed');draw=ImageDraw.Draw(sheet)
        draw.text((12,7),f'电脑预测  |  {unit}  配方 {slot:02d}  {NAMES[param]}  {method if param in ("warmth","tint","tone") else ""}',font=f_title,fill='#171b19')
        note='固定 ISO 200 A12-50 前向模型；DNG CFA 缩图，曝光与白平衡不随档位改变。'
        if unit!='jlaunch':note+=' 跨单元模型尚未验证。'
        if param=='tone':note='电脑预测：假设黑白矩阵色度旁路颜色表；现有 Engine 不支持 Tone，偏置单位也未经验证。'
        if param=='amount' and slot==4:note='电脑预测：04 等于原厂端点，Amount 全部档位相同。'
        draw.text((12,43),note,font=f_text,fill='#414740')
        rendered={};variant_bytes={}
        for level in sorted(int(z) for z in g['doses']):
            variant_bytes[level]=c.apply(stock,base,level_request(g,level))[0]
        for scene_num,scene in enumerate(scenes):
            scene_id=scene['id'];x,size=inputs[scene_id];sample=samples[scene_id]
            regions=masks(model,base,sample,param);labs={};rgbs={}
            for level,b in variant_bytes.items():
                rgb=model.predict(b,sample,quantize=True);rgbs[level]=rgb;labs[level]=model.lab(rgb)
            ordered=sorted(variant_bytes)
            for j in range(1,len(ordered)):
                a,b=ordered[j-1:j+1];de=model.de(labs[a],labs[b]);whole=stats(de)
                for region_num,region in enumerate(regions):
                    part=stats(de[region]);metric_rows.append(dict(unit=unit,slot=slot,param=param,alternative=alt,method=method,
                         scene=scene_id,from_level=a,to_level=b,region=region_num,region_n=part['n'],
                         region_median=part['median'],region_mean=part['mean'],region_p90=part['p90'],region_fraction_ge_1=part['fraction_ge_1'],
                         full_median=whole['median'],full_mean=whole['mean'],byte_dead=variant_bytes[a]==variant_bytes[b],
                         conditional=param=='tone',transfer_model=unit!='jlaunch'))
            for col,level in enumerate(levels):
                b=variant_bytes[level]
                rgb=model.predict(b,x,quantize=True)
                cell=Image.fromarray(rgb.reshape(size[1],size[0],3),'RGB')
                px,py=col*width,92+scene_num*(height+38)
                sheet.paste(cell,(px,py));label=f'{level}%' if param=='amount' else f'{level:+d}'
                draw.text((px+5,py+height+4),f'{scene_id}  {label}  电脑预测',font=f_text,fill='#171b19')
                if level==(100 if param=='amount' else 0):draw.rectangle((px,py,px+width-1,py+height-1),outline='#936b2d',width=2)
                records.append(dict(unit=unit,slot=slot,param=param,alternative=alt,method=method,scene=scene_id,level=level,
                                    dose=g['doses'][str(level)],entry_sha256=hashlib.sha256(b).hexdigest(),
                                    display_RGB_sha256=hashlib.sha256(rgb.tobytes()).hexdigest(),
                                    computer_prediction=True,conditional=param=='tone',sheet=name))
        meta=PngImagePlugin.PngInfo();meta.add_itxt('Title','电脑预测 '+name)
        meta.add_itxt('Description',note)
        sheet.save(folder/name,pnginfo=meta,optimize=False)
        index.append(dict(unit=unit,slot=slot,param=param,alternative=alt,method=method,path='local/previews/'+name,
                          computer_prediction=True,conditional=param=='tone',width=sheet.width,height=sheet.height))
        # Direction on neutral input, measured after the colour chain and display clipping.
        if param in ('warmth','tint','split','tone'):
            neutral=np.repeat(np.geomspace(5,3500,257)[:,None],3,axis=1)
            zero=model.predict(base,neutral,quantize=True);la0=model.lab(zero);y=model.mm.ycbcr(zero)[0]
            for level in (-9,-1,1,9):
                rgb=model.predict(variant_bytes[level],neutral,quantize=True);lab=model.lab(rgb)
                regs=[(y>=35)&(y<=220)] if param!='split' else [(y>=20)&(y<=90),(y>=160)&(y<=235)]
                for reg_num,reg in enumerate(regs):
                    da=lab[reg,1]-la0[reg,1];db=lab[reg,2]-la0[reg,2]
                    axis=da if param=='tint' else db;desired=1 if level>0 else -1
                    if param=='split' and reg_num==0:desired=-desired
                    directions.append(dict(unit=unit,slot=slot,param=param,alternative=alt,method=method,level=level,
                         region=reg_num,n=int(reg.sum()),median_delta_a=float(np.median(da)),median_delta_b=float(np.median(db)),
                         expected_sign=desired,median_direction_correct=bool(float(np.median(axis))*desired>0),conditional=param=='tone'))
        if (group_num+1)%9==0 or group_num+1==len(main_groups+alternatives):
            print(f'preview sheets {group_num+1}/{len(main_groups+alternatives)}: {time.monotonic()-start:.1f}s',flush=True)
    for filename,rows in (('scene_adjacent.csv',metric_rows),('directions.csv',directions),('previews/index.csv',index)):
        with (s.LOCAL/filename).open('w',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    s.dump(s.LOCAL/'preview_frames.json',records)
    s.dump(s.LOCAL/'preview_index.json',index)
    for item in index:
        p=s.HERE/item['path']
        with Image.open(p) as im:
            assert '电脑预测' in im.info['Title'] and im.size==(1372,772)
            im.verify()
    s.dump(s.LOCAL/'model_inputs_previews.json',model.provenance());s.verify_inputs()
    s.dump(s.LOCAL/'preview_verification.json',dict(PNGs=len(index),cells=len(records),adjacent_region_records=len(metric_rows),
             PNG_decode_and_label='PASS',model_simulation_not_capture=True,conditional_BW_Tone=True,elapsed_seconds=time.monotonic()-start))
    print('DONE',len(index),'PNGs',len(records),'cells',flush=True)

if __name__=='__main__':main()
