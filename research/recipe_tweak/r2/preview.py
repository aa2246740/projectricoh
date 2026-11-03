#!/usr/bin/env python3
"""Five real DNG fixtures; all output images are model simulations."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import ast
import csv
import hashlib
import json
from collections import defaultdict
import numpy as np
from PIL import Image, ImageDraw, ImageOps
import runtime as r
import tweak as t

WIDTH = 320
LABELS = dict(zip(t.PARAMETERS, ("对比", "饱和", "高光", "阴影", "冷暖", "色调")))
DISPLAY_LEVELS = (-8, -5, -3, -1, 0, 1, 3, 5, 8)
SCENES = (
    ("desk", "红印纸与桌面", "2026-10-16/S1b-sd-import/DCIM/100RICOH/R8051130"),
    ("neutral", "灰墙与笔", "2026-10-16/S1b-sd-import/DCIM/100RICOH/R8051137"),
    ("apple", "苹果与杂物", "2026-10-19/stage2c-first-run/R8051144"),
    ("redblue", "红苹果与蓝色卡片近景", "2026-10-19/stage2c-first-run/R8051145"),
    ("redclose", "红苹果与印纸近景", "2026-10-19/stage2c-first-run/R8051147"),
)


def load_r1_render_functions():
    path = r.HERE.parent / "preview.py"
    tree = ast.parse(path.read_text())
    names = {"raw_input", "predict", "statistics", "save_frame"}
    module = ast.Module(body=[n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names], type_ignores=[])
    exec(compile(module, str(path), "exec"), globals())


def wb_gains(warmth, tint):
    # An explicit illustration only. The native gain per WB tick is unknown.
    return np.exp2(np.array([warmth / 12 + tint / 24, -tint / 12, -warmth / 12 + tint / 24]))


def html(frames, scenes, aggregates):
    data = dict(frames=frames, scenes=scenes, aggregates=aggregates, labels=LABELS, display=DISPLAY_LEVELS)
    template = (r.HERE / "preview_template.html").read_text()
    (r.LOCAL / "preview.html").write_text(template.replace("__DATA__", json.dumps(data, ensure_ascii=False)))


def main():
    r.setup(); load_r1_render_functions()
    src, _, base, entries = r.baseline()
    verified = json.loads((r.LOCAL / "variants.json").read_text())
    assert verified["schema"] == t.ALGORITHM
    pivot = verified["pivot_x"]
    variants = {(v["slot"], v["parameter"], v["level"]): v for v in verified["variants"]}
    engine = r.engine(iso=200); fs = engine.fs
    assert abs(float(fs.delta_e00(np.array([[50,2.6772,-79.7751]]),np.array([[50,0,-82.7485]]))[0])-2.0425)<0.00005
    for folder in ("frames", "contacts"): (r.LOCAL / folder).mkdir(exist_ok=True)
    dependencies = {str(p.relative_to(r.ROOT)): r.sha(p) for p in
        (r.HERE / "tweak.py", r.HERE / "preview.py", r.HERE / "preview_template.html",
         r.HERE.parent / "preview.py", r.ROOT / "research/closed_loop/model.py", r.TABLE)}
    all_frames, metrics, scenes, step_ratios = [], [], [], []
    r1 = r.load("r1_reference_tweak", r.HERE.parent / "tweak.py")
    for scene_id, title, rel in SCENES:
        path = r.ROOT / "captures/a12-50" / rel
        dng_path, jpeg_path = path.with_suffix(".DNG"), path.with_suffix(".JPG")
        for p in (dng_path,jpeg_path): dependencies[str(p.relative_to(r.ROOT))] = r.sha(p)
        dng=fs.dsm().Dng(dng_path); x,size,input_info=raw_input(dng)
        source=ImageOps.exif_transpose(Image.open(jpeg_path)).convert("RGB").resize(size,Image.Resampling.LANCZOS)
        source_path=f"frames/{scene_id}-source.png"; source.save(r.LOCAL/source_path,optimize=True)
        scene=dict(id=scene_id,title=title,stem=path.name,path=rel,iso=dng.exif["iso"],size=list(size),
                   source_image=source_path,input=input_info,dng=dng.summary(),calibration_iso=200)
        scenes.append(scene)
        for slot in r.SLOTS:
            entry=entries[slot]; idx=src.TABLE_SLOTS.index(int(slot))
            default_raw=base[16+idx*448:16+(idx+1)*448]
            base_raw=predict(engine,slot,entry["rows"],x); base_rgb=np.clip(base_raw,0,255)
            base_lab=fs.lab_from_codes(base_rgb); y=engine.mm.ycbcr(base_rgb)[0]
            chroma=np.hypot(base_lab[:,1],base_lab[:,2]); chromatic=chroma>=10
            masks={"contrast":np.ones(len(x),bool),"saturation":chromatic,
                   "highlight":y>=118,"shadow":y<118,
                   "warmth":(chroma<10)&(y>=20)&(y<=235),"tint":(chroma<10)&(y>=20)&(y<=235)}
            cache={}; zero_clip=float(np.any((base_raw<0)|(base_raw>255),axis=1).mean())
            for parameter in t.PARAMETERS:
                outputs=[]; group_frames=[]
                for level in range(-8,9):
                    lev=t.Levels(**{parameter:level}); rows,info=t.apply(entry,lev,pivot)
                    v=variants[slot,parameter,level]
                    assert t.encode_entry(default_raw,rows).hex()==v["entry_hex"]
                    key=(v["entry_hex"],lev.warmth,lev.tint)
                    if key not in cache:
                        raw=predict(engine,slot,rows,x*wb_gains(lev.warmth,lev.tint))
                        assert np.isfinite(raw).all()
                        rgb=np.clip(raw,0,255); filename=f"frames/{scene_id}-{slot}-{parameter}-{level:+d}.png"
                        save_frame(rgb,size,r.LOCAL/filename)
                        cache[key]=(rgb,filename,float(np.any((raw<0)|(raw>255),axis=1).mean()))
                    rgb,filename,clip=cache[key]; outputs.append(rgb)
                    frame=dict(scene=scene_id,slot=slot,parameter=parameter,level=level,image=filename,
                        model_simulation_not_capture=True,WB_approximate=parameter in ("warmth","tint"),
                        saturation=info,model_rgb_clip_fraction=clip,default_rgb_clip_fraction=zero_clip,
                        adjacent_previous=None,rgb_float_sha256=hashlib.sha256(rgb.astype('<f8').tobytes()).hexdigest())
                    all_frames.append(frame); group_frames.append(frame)
                labs=[fs.lab_from_codes(o) for o in outputs]
                for j in range(16):
                    e=fs.delta_e00(labs[j],labs[j+1]); region=e[masks[parameter]]
                    result=dict(scene=scene_id,slot=slot,parameter=parameter,from_level=j-8,to_level=j-7,
                        full=statistics(e),region=statistics(region),region_kind={"contrast":"whole image",
                        "saturation":"default C* >= 10","highlight":"default Y >= 118",
                        "shadow":"default Y < 118","warmth":"default C* < 10 and 20 <= Y <= 235",
                        "tint":"default C* < 10 and 20 <= Y <= 235"}[parameter],
                        fraction_above_1=float((e>=1).mean()),fraction_above_3=float((e>=3).mean()))
                    group_frames[j+1]["adjacent_previous"]=dict(full=result["full"],region=result["region"])
                    metrics.append(result)
                # Same float domain, same inputs and masks for the R1-to-R2 step comparison.
                if parameter in ("contrast","saturation","highlight","shadow") and scene_id in ("desk","neutral","apple"):
                    for level in (-1,1):
                        old_rows,_=r1.apply(entry,r1.Levels(**{parameter:level}),pivot)
                        old_lab=fs.lab_from_codes(np.clip(predict(engine,slot,old_rows,x),0,255))
                        new_lab=labs[level+8]
                        old_e=fs.delta_e00(base_lab,old_lab); new_e=fs.delta_e00(base_lab,new_lab)
                        old_full=float(old_e.mean());new_full=float(new_e.mean())
                        mask=masks[parameter]; old_region=float(old_e[mask].mean()) if mask.any() else None
                        new_region=float(new_e[mask].mean()) if mask.any() else None
                        step_ratios.append(dict(scene=scene_id,slot=slot,parameter=parameter,level=level,
                            r1_full=old_full,r2_full=new_full,full_ratio=new_full/old_full if old_full>1e-8 else None,
                            r1_region=old_region,r2_region=new_region,
                            region_ratio=new_region/old_region if old_region and old_region>1e-8 else None))
            # One inspectable sheet per recipe, all six parameters, requested nine levels.
            height=size[1]; sheet=Image.new('RGB',(WIDTH*9,(height+30)*6+48),'#f4f3ef'); draw=ImageDraw.Draw(sheet)
            draw.text((8,8),f'{scene_id} / recipe {slot} | MODEL SIMULATION, NOT CAMERA CAPTURE | WB APPROXIMATE',fill='#20211f')
            for row,param in enumerate(t.PARAMETERS):
                for col,level in enumerate(DISPLAY_LEVELS):
                    f=next(q for q in all_frames if (q['scene'],q['slot'],q['parameter'],q['level'])==(scene_id,slot,param,level))
                    xx,yy=WIDTH*col,48+(height+30)*row
                    with Image.open(r.LOCAL/f['image']) as im: sheet.paste(im,(xx,yy))
                    draw.text((xx+5,yy+height+7),f'{param} {level:+d}',fill='#20211f')
            sheet.save(r.LOCAL/'contacts'/f'{scene_id}-{slot}.jpg',quality=88)
        print(f"rendered {scene_id}: 5 recipes, 6 controls, 17 levels",flush=True)
    aggregates=[]
    for slot in r.SLOTS:
        for param in t.PARAMETERS:
            group=[m for m in metrics if m['slot']==slot and m['parameter']==param]
            adjacent=[]
            for level in range(-8,8):
                g=[m for m in group if m['from_level']==level]
                reg=[m['region']['mean'] for m in g if m['region']['n']]
                adjacent.append(dict(from_level=level,to_level=level+1,full_mean=float(np.mean([m['full']['mean'] for m in g])),
                                     region_mean=float(np.mean(reg)) if reg else None,region_scene_count=len(reg)))
            aggregates.append(dict(slot=slot,parameter=param,adjacent=adjacent))
    assert len(all_frames)==2550 and len(metrics)==2400
    # First-round T1 adapter degenerates exactly to Engine when C=B=D.
    rows=list(entries['06']['rows']); rows[6]=rows[1]*2
    adapted=predict(engine,'06',tuple(rows),x[:1000]); old=engine.entries['06']
    engine.entries['06']=dict(old,mask=old['mask']&~6,control=2)
    try: shared=predict(engine,'06',tuple(rows),x[:1000])
    finally: engine.entries['06']=old
    adapter_error=float(np.max(np.abs(adapted-shared))); assert adapter_error<1e-10
    assert all(r.sha(r.ROOT/p)==h for p,h in dependencies.items())
    provenance=engine.provenance.finish()
    r.dump(r.LOCAL/'frames.json',all_frames)
    r.dump(r.LOCAL/'metrics.json',dict(model_simulation_not_capture=True,WB_approximate=True,scenes=scenes,
        pairs=metrics,aggregates=aggregates,frames=len(all_frames),T1_adapter_max_RGB_error=adapter_error,
        metric_domain='clipped float model RGB, sRGB/D65 Lab, 320px reduced CFA, fixed ISO200 calibration'))
    r.dump(r.LOCAL/'step_ratio_r1.json',step_ratios)
    r.dump(r.LOCAL/'preview_inputs.json',dict(direct=dependencies,engine=provenance))
    with (r.LOCAL/'adjacent_delta_e00.csv').open('w',newline='') as stream:
        keys=('scene','slot','parameter','from_level','to_level','full_mean','full_p90','region_n','region_mean','region_p90','region_kind')
        writer=csv.DictWriter(stream,fieldnames=keys);writer.writeheader()
        for m in metrics:
            writer.writerow({**{k:m[k] for k in keys if k in m},'full_mean':m['full']['mean'],'full_p90':m['full']['p90'],
                             'region_n':m['region']['n'],'region_mean':m['region']['mean'],'region_p90':m['region']['p90']})
    html(all_frames,scenes,aggregates)
    print(json.dumps(dict(frames=len(all_frames),adjacent_pairs=len(metrics),T1_equivalence=adapter_error)))


if __name__=='__main__': main()
