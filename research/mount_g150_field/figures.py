"""Deterministic comparison figures using measured JPEGs and labeled model data."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import analyze as a
import json
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps

FONT='/System/Library/Fonts/Hiragino Sans GB.ttc'
BG=(247,247,244)
INK=(25,28,30)


def font(n): return ImageFont.truetype(FONT,n)


def text(im,xy,s,size=22,fill=INK):
    ImageDraw.Draw(im).text(xy,s,font=font(size),fill=fill)


def rectified(stem,width):
    f=json.loads((a.HERE/'charts'/(stem+'.json')).read_text())
    layout=json.loads((a.ROOT/'research/chart_v2/patches.json').read_text())
    W,H=layout['canvas_px'];height=round(width*H/W)
    M=np.array(f['geometry']['H']) @ np.diag([W/width,H/height,1])
    M/=M[2,2]
    coeff=M.flatten()[:8]
    with Image.open(a.CAP/(stem+'.JPG')) as src:
        return src.convert('RGB').transform((width,height),Image.Transform.PERSPECTIVE,coeff,
            resample=Image.Resampling.BICUBIC)


def compare():
    slots=['04','01','02','03','05','06']
    names={'04':'Std 标准','01':'GR 正片','02':'GR 负片','03':'HC 黑白','05':'F-CC','06':'F-CN'}
    now=dict(zip(slots,range(1693,1699)))
    old={'04':1533,'01':1530,'02':1531,'03':1532,'05':1534,'06':1535}
    data=json.loads((a.HERE/'chart_metrics.json').read_text())
    width,gap,margin=420,12,28
    total=margin*2+width*6+gap*5
    out=Image.new('RGB',(total,895),BG)
    text(out,(margin,15),'MOUNT g150：同一页色卡的六个配方',34)
    text(out,(margin,65),'相机实拍；保持原始亮度与颜色，仅校正透视和缩放。',23)
    top=150
    for i,s in enumerate(slots):
        x=margin+i*(width+gap)
        text(out,(x,110),s+' '+names[s],27)
        im=rectified(f'R805{now[s]}',width)
        out.paste(im,(x,top))
        m=data[s]['anchors']['ANCHOR_midgray']
        text(out,(x,top+im.height+8),f"R805{now[s]} · ISO 200 · 1/60",20)
        text(out,(x,top+im.height+38),f"中灰 L* {m['camera_L']:.1f}；相对 04 {m['camera_dL_vs04']:+.1f}",20)
    y=top+round(width*2234/3456)+95
    text(out,(margin,y),'10-31 MOUNT g137 街拍参照：场景、曝光和白平衡不同，只作观感参照。',25)
    y+=45
    for i,s in enumerate(slots):
        x=margin+i*(width+gap)
        with Image.open(a.ROOT/f'captures/street-g137-20261031/jpg/R805{old[s]}.JPG') as src:
            im=src.convert('RGB');im.thumbnail((width,280),Image.Resampling.LANCZOS)
            out.paste(im,(x,y))
        text(out,(x,y+im.height+8),f'R805{old[s]} · {s} · ISO 800',21)
    path=a.CAP/'compare.jpg'
    out.save(path,quality=94,subsampling=0)
    print(path, out.size, flush=True)


def target_chart(labs,supported,width):
    layout=json.loads((a.ROOT/'research/chart_v2/patches.json').read_text())
    pp=[p for p in layout['patches'] if p['page']==1]
    assert len(pp)==len(labs)
    gap=a.load('figure_gap','research/gr_posneg_gap/common.py')
    import os
    os.environ['TMPDIR']=str(a.TMP)
    W,H=layout['canvas_px'];height=round(width*H/W)
    out=Image.new('RGB',(width,height),(12,12,12));draw=ImageDraw.Draw(out)
    rgb=np.zeros_like(labs)
    rgb[supported]=gap.rgb(labs[supported])
    outgamut=supported&((rgb<0).any(1)|(rgb>255).any(1))
    for i,p in enumerate(pp):
        x0,y0,x1,y1=p['bbox_px'];r=[round(x0/W*width),round(y0/H*height),round(x1/W*width),round(y1/H*height)]
        if supported[i]:
            col=tuple(np.clip(np.round(rgb[i]),0,255).astype('uint8'))
            draw.rectangle(r,fill=col)
        else:
            draw.rectangle(r,fill=(55,55,55))
            draw.line([r[0],r[1],r[2],r[3]],fill=(125,125,125),width=1)
            draw.line([r[2],r[1],r[0],r[3]],fill=(125,125,125),width=1)
    a.dump('figure_target_gamut.json',dict(supported=int(supported.sum()),display_clipped=int(outgamut.sum()),
        scoring_uses_original_Lab=True,unsupported_not_scored=True))
    return out


def compare_grn():
    z=np.load(a.HERE/'griv_grn_patches.npz')
    width,gap,margin=560,18,28
    out=Image.new('RGB',(2*margin+4*width+3*gap,585),BG)
    text(out,(margin,15),'GRN*001 留银冲洗：按表出片，但与 GR IV 目标仍有明显差距',31)
    text(out,(margin,65),'本页 62 个有效且受目标支持的色块：ΔE00 中位 12.24，评分 42.0%；亮度中位低 11.40 L*。',23)
    titles=['04 标准 · 相机实拍','02 负片 · 相机实拍','GRN*001 · 相机实拍','GR IV 留银冲洗 · 颜色目标预测']
    pics=[rectified('R8051693',width),rectified('R8051695',width),rectified('R8051701',width),
          target_chart(z['target_lab'],z['supported'],width)]
    for i,(name,pic) in enumerate(zip(titles,pics)):
        x=margin+i*(width+gap)
        text(out,(x,115),name,24)
        out.paste(pic,(x,157))
    text(out,(margin,533),'目标图中的叉号表示不在目标支持内；显示颜色限制在 sRGB 范围，评分仍用原始 Lab。',23)
    path=a.CAP/'compare-grn.jpg';out.save(path,quality=94,subsampling=0)
    print(path,out.size,flush=True)


def compare_scenes():
    width,height,gap,margin=660,440,18,28
    out=Image.new('RGB',(2*margin+3*width+2*gap,3*(height+52)+130),BG)
    text(out,(margin,12),'同一张 RAW：01 正片实拍、04 标准预测、01 表预测',31)
    text(out,(margin,56),'1703–1705 均识别为 01；预测列为小区域均值渲染，实拍列只缩放。',22)
    cols=['01 相机实拍','04 标准 · 电脑预测','01 正片 · 电脑预测']
    for row,n in enumerate((1703,1704,1705)):
        y=102+row*(height+52)
        stem=f'R805{n}'
        z=np.load(a.HERE/'samples'/(stem+'-dense.npz'))
        with Image.open(a.CAP/(stem+'.JPG')) as src:
            act=src.convert('RGB').resize((width,height),Image.Resampling.LANCZOS)
        pics=[act,Image.fromarray(np.clip(np.round(z['stock04']),0,255).astype('uint8')).resize((width,height),Image.Resampling.BICUBIC),
              Image.fromarray(np.clip(np.round(z['recipe']),0,255).astype('uint8')).resize((width,height),Image.Resampling.BICUBIC)]
        for i,(title,pic) in enumerate(zip(cols,pics)):
            x=margin+i*(width+gap)
            text(out,(x,y),f'{stem} · {title}',24)
            out.paste(pic,(x,y+36))
    path=a.CAP/'compare-scenes.jpg';out.save(path,quality=93,subsampling=0)
    print(path,out.size,flush=True)


if __name__=='__main__':
    compare();compare_grn();compare_scenes();a.finish('figures')
