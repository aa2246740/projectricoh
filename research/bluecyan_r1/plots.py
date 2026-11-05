#!/usr/bin/env python3
"""Statistics-only plots with the repository's existing Pillow plotting tool."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import analyze as a
from analyze import np,LOCAL,ROOT,read
from PIL import Image,ImageDraw

p=a.module('blue_pilplot',ROOT/'research/hue_ring/pilplot.py')


def error_color(value):
    stops=np.array([[30,61,92],[36,125,139],[68,167,124],[240,185,70],[190,52,48]])
    at=np.clip(value/10,0,1)*4;lo=min(int(at),3);t=at-lo
    return tuple(np.rint((1-t)*stops[lo]+t*stops[lo+1]).astype(int))


def main():
    rows=read(LOCAL/'physical/noon-patches.json')
    w,h=650,360;sheet=Image.new('RGB',(2*w+80,2*h+65),p.SURFACE)
    for i,name in enumerate(('05 F-CC','06 F-CN')):
      rr=[r for r in rows if r['setting']==name and r['kind']=='screen']
      for j,field in enumerate(('old_error','physical_error')):
        plot=p.Plot(w,h,(0,360),(0,65),name+(' | shared 50mm nodes' if j==0 else ' | native MOUNT C040'),
            'Pre-table CbCr hue (degrees)','Chroma (codes)',margins=(64,52,18,52))
        plot.axes(np.arange(0,361,60),np.arange(0,61,15))
        for split,shape,size in (('T','o',7),('V','^',8)):
            for r in [r for r in rr if r['split']==split]:
                plot.points([r['physical_input_hue']],[r['physical_input_chroma']],error_color(r[field]),shape=shape,size=size)
        sheet.paste(plot.im,(j*w,i*h))
    draw=ImageDraw.Draw(sheet);f=p.font(16)
    draw.text((25,2*h+10),'Circles: T pages. Triangles: V pages. All 382 valid screen patches per recipe.',fill=p.INK,font=f)
    for y in range(40,2*h-70):
        value=10*(1-(y-40)/(2*h-110));draw.line((2*w+18,y,2*w+39,y),fill=error_color(value),width=1)
    for value in (0,2,4,6,8,10):
        y=40+(1-value/10)*(2*h-110);draw.text((2*w+44,y),str(value),fill=p.INK,font=p.font(14),anchor='lm')
    draw.text((2*w+6,2*h-37),'DE00',fill=p.INK,font=p.font(14))
    sheet.save(LOCAL/'residual-hue-chroma.png')

    scores=read(LOCAL/'physical/noon-scores.json')
    names=['05 F-CC','06 F-CN','M9 STD','HNCS HiCon','Kodachrome25','HNCS LowSat','Vision3 500T']
    sheet=Image.new('RGB',(1360,450),p.SURFACE)
    for col,split in enumerate(('V','card')):
        plot=p.Plot(680,450,(0,9),(-.8,7),'V pages held out' if split=='V' else 'Physical card held out',
            'D50 DE00. Circle = median; right cap = P95.','',margins=(145,56,20,65))
        plot.axes(np.arange(0,10),[])
        for i,name in enumerate(names):
            y=6-i;plot.d.text((132,plot.y(y)),name,fill=p.INK,font=p.font(14),anchor='rm')
            for key,offset,color in (('old',.12,(211,154,88)),('physical',-.12,(58,129,172))):
                v=scores[name+' '+split][key]
                plot.hbar(v['median'],v['p95'],y+offset,color,width=3,cap=4)
                plot.points([v['median']],[y+offset],color,size=9)
        plot.legend_top([('Old model',(211,154,88),'o'),('Native C040',(58,129,172),'o')])
        sheet.paste(plot.im,(col*680,0))
    sheet.save(LOCAL/'heldout-model-errors.png')

    plot=p.Plot(1100,400,(0,23),(0,370),'Module-native C040 geometry',
                'C080 sector index (zero based)','Peak angle (degrees)',margins=(70,55,25,55))
    plot.axes(np.arange(0,24,2),np.arange(0,361,60))
    legend=[]
    for unit,color,label in (('a12-50',(211,154,88),'50mm source'),('mount-a12',(58,129,172),'MOUNT native'),('a12-28',(113,156,113),'28mm native')):
        spec=read(LOCAL/f'physical/ring-{unit}-200.json');x=np.arange(24);y=spec['nodes_unwrapped_deg']
        plot.line(x,y,color,width=2);plot.points(x,y,color,size=7);legend.append((label,color,'o'))
    plot.legend_top(legend);plot.save(LOCAL/'native-node-geometry.png')
    print('Pillow statistics plots written; no dependency installation',flush=True)


if __name__=='__main__':main()
