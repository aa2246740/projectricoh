"""Create a self-contained interactive comparison using aggregate measurements only."""
import argparse
import json
from pathlib import Path
import sys

assert sys.flags.isolated
HERE=Path(__file__).resolve().parent
LOCAL=HERE/'local'

PAGE='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<style>
:root {font-family:var(--font-sans,system-ui,sans-serif);color:var(--foreground,#202124)}
body {margin:0} .controls {display:flex;gap:12px;flex-wrap:wrap;align-items:center;margin:8px 0 14px}
select {font:inherit;color:var(--foreground,#202124);background:var(--secondary,#f3f4f6);border:1px solid var(--border,#d1d5db);border-radius:var(--radius,6px);padding:6px}
.legend {display:flex;gap:16px;font-size:12px;color:var(--muted-foreground,#60656d);margin-bottom:8px}
.dot {display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:5px;background:var(--chart-1,#3972ba)}
.dot.full {background:var(--chart-2,#b46732)}
.chart {overflow-x:auto}svg {display:block;width:100%;min-width:600px;height:810px}
svg text {font-family:var(--font-sans,system-ui,sans-serif);fill:var(--foreground,#202124);font-size:12px}
svg .muted {fill:var(--muted-foreground,#60656d);font-size:11px}
svg .grid {stroke:var(--border,#d1d5db);stroke-width:1}svg .link {stroke:var(--muted-foreground,#60656d);stroke-width:2;opacity:.45}
svg .left {fill:var(--chart-1,#3972ba)}svg .full {fill:var(--chart-2,#b46732)}
.note {font-size:12px;line-height:1.6;color:var(--muted-foreground,#60656d);margin:10px 0}
.detail {background:var(--card,#f6f7f8);border:1px solid var(--border,#d1d5db);border-radius:var(--radius,6px);padding:16px;font-size:13px;line-height:1.6;min-height:42px}
</style>
<body><div class="controls"><label>单元 <select id="unit"><option value="a12-50">50mm</option><option value="a12-28">28mm</option><option value="mount-a12">MOUNT</option></select></label>
<label>对照 <select id="route"><option value="Look">Look 共享曲线</option><option value="black">满配黑盒初始化</option><option value="structure">满配结构代理</option><option value="weighted">满配敏感色加权</option></select></label></div>
<div class="legend"><span><i class="dot"></i><span id="left-label">Look 共享曲线</span></span><span><i class="dot full"></i>满配，未加权训练优选</span></div>
<div class="chart"><svg id="plot" role="img" aria-label="20种胶片在同一场景光目标下的对照分数"></svg></div>
<div id="detail" class="detail">点选胶片名称或分数点，查看绝对余差、量化与位置判断。</div>
<p class="note">分数是相对原厂 04 的中位 ΔE00 改善百分比，不是主观像胶片评分。全部为 native C040 电脑照片留出。一点是所选对照，另一点是训练选中的满配记录；量化未全过的记录未准入。结构代理没有使用真实分层密度。</p>
<script>
const DATA=__DATA__;
const NS='http://www.w3.org/2000/svg';
function elt(tag,attrs,text){const e=document.createElementNS(NS,tag);for(const [k,v]of Object.entries(attrs))e.setAttribute(k,v);if(text!==undefined)e.textContent=text;return e}
const number=x=>x===null?'无定义':x.toFixed(2);
function draw(){
 const unit=document.getElementById('unit').value,route=document.getElementById('route').value;
 const select=document.getElementById('route');document.getElementById('left-label').textContent=select.options[select.selectedIndex].text;
 const svg=document.getElementById('plot');svg.replaceChildren();svg.setAttribute('viewBox','0 0 710 810');
 const all=DATA.flatMap(d=>[d.units[unit][route],d.units[unit].full]).filter(x=>x!==null);
 const low=Math.min(0,Math.floor(Math.min(...all)/10)*10),high=Math.max(100,Math.ceil(Math.max(...all)/10)*10);
 const x=v=>153+(v-low)/(high-low)*470;
 for(let tick=Math.ceil(low/20)*20;tick<=high;tick+=20){svg.append(elt('line',{x1:x(tick),x2:x(tick),y1:27,y2:786,class:'grid'}));svg.append(elt('text',{x:x(tick),y:17,'text-anchor':'middle',class:'muted'},tick+'%'))}
 DATA.forEach((d,i)=>{
  const row=d.units[unit],a=row[route],b=row.full,y=48+i*38;
  const group=elt('g',{tabindex:0,role:'button','aria-label':d.name+' 查看数据'});
  group.append(elt('text',{x:0,y:y+4},d.name));
  if(a!==null&&b!==null){group.append(elt('line',{x1:x(a),x2:x(b),y1:y,y2:y,class:'link'}));group.append(elt('circle',{cx:x(a),cy:y,r:4.4,class:'left'}));group.append(elt('circle',{cx:x(b),cy:y,r:4.4,class:'full'}))}
  group.append(elt('text',{x:705,y:y+4,'text-anchor':'end',class:'muted'},number(a)+' / '+number(b)));
  const detail=()=>document.getElementById('detail').textContent=d.name+' · '+d.provider+'。满配中位 / P95 ΔE00 '+number(row.median)+' / '+number(row.p95)+'；量化 '+row.quant+'/128；'+(d.safe?'三单元数值上 Look 安全':'需要满配或仍有位置风险')+'。'+(d.policy?'彩色胶片按策略放满配。':'')+(row.defaultEligible?'通过模型量化与灰轴诊断；待主机/相机验收。':row.grayWarning?'灰轴有额外回落，暂不列默认。':'未通过本轮完整研究准入门。');
  group.style.cursor='pointer';group.addEventListener('click',detail);group.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();detail()}});
  svg.append(group);
 });
}
document.getElementById('unit').addEventListener('change',draw);document.getElementById('route').addEventListener('change',draw);draw();
</script></body></html>'''


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--require-complete',action='store_true');args=parser.parse_args()
    summary=json.loads((LOCAL/'summary.json').read_text())
    if args.require_complete:assert summary['complete']
    data=[]
    for film in summary['films']:
        if not film['complete']:continue
        units={}
        for unit,row in film['units'].items():
            doc=json.loads(Path(row['analysis_file']).read_text())
            values={name:doc['routes'][route]['scores']['photo_iso200']['similarity_percent']
                    for name,route in (('black','scene_rgb_matrix'),('structure','scene_structure'),('weighted','scene_weighted'))}
            units[unit]=dict(values,Look=row['Look']['similarity_percent'],full=row['full']['similarity_percent'],
                             median=row['full']['de00']['median'],p95=row['full']['de00']['p95'],
                             quant=row['quantization_passes'],robust=row['robust_model_candidate'],
                             defaultEligible=row['default_shortlist_eligible'],grayWarning=row['gray_shape_warning'])
        data.append(dict(name=film['name'],provider=film['provider'],units=units,
                         safe=film['numerical_Look_safe'],policy=film['policy_full']))
    html=PAGE.replace('__DATA__',json.dumps(data,ensure_ascii=False,allow_nan=False).replace('</','<\\/'))
    path=LOCAL/'comparison.html';path.write_text(html)
    print(path,len(data),'films')


if __name__=='__main__':main()
