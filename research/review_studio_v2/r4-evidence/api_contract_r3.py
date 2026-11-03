"""COPY 3.13 request-only errors, plus inherited versus explicitly disabled finish."""
from pathlib import Path
import csv,io,json,sys
ROOT=Path('/Volumes/Workspace/Scratch/tmp/projectricoh/review-studio-v2-r4');E=ROOT/'evidence'
import httpx
from PIL import Image
ready=json.loads((ROOT/'server-ready.json').read_text());assert ready['port']!=49667
c=httpx.Client(base_url=f"http://127.0.0.1:{ready['port']}",headers={'X-GXR-Token':'independent-review-browser'},timeout=240)
photos={p['name']:p for p in c.get('/api/photos').json()};sid=photos['REVIEW']['id']
cases=[('render-quality','GET',f'/api/photos/{sid}/render?stage=final&size=preview&quality=29',None,'src/gxr_studio/api/render_routes.py:170')]
for name,body,line in [
 ('adjust-float',{'adjust':{'contrast':0.5}},'render/params.py:113'),
 ('adjust-range',{'adjust':{'contrast':101}},'render/params.py:116'),
 ('adjust-key',{'adjust':{'nope':1}},'render/params.py:127'),
 ('exposure-range',{'adjust':{'exposure_ev':6}},'render/params.py:130'),
 ('curve-key',{'curve':{'red':[[0,0],[255,255]]}},'render/params.py:153'),
 ('curve-size',{'curve':{'master':[[0,0]]}},'render/params.py:158'),
 ('curve-point',{'curve':{'master':[[0,0],[256,255]]}},'render/params.py:166'),
 ('curve-order',{'curve':{'master':[[0,0],[0,20],[255,255]]}},'render/params.py:169'),
 ('recipe-kind',{'recipe':{'kind':'custom'}},'render/params.py:181'),
 ('recipe-unit',{'recipe':{'unit':'invalid','slot':1}},'render/params.py:184'),
 ('recipe-slot',{'recipe':{'unit':'jlaunch','slot':9}},'render/params.py:186'),
 ('recipe-knob',{'recipe':{'unit':'jlaunch','slot':1,'levels':{'nope':1}}},'render/params.py:193'),
 ('recipe-level',{'recipe':{'unit':'jlaunch','slot':1,'levels':{'contrast':0.5}}},'render/params.py:196'),
 ('geometry-range',{'geometry':{'straighten':46}},'finish/spec.py:106'),
 ('geometry-float',{'geometry':{'vertical':0.5}},'finish/spec.py:113'),
 ('geometry-key',{'geometry':{'nope':1}},'finish/spec.py:125'),
 ('geometry-rotate',{'geometry':{'rotate90':4}},'finish/spec.py:128'),
 ('geometry-flip',{'geometry':{'flip':'bad'}},'finish/spec.py:131'),
 ('frame-style',{'frame':{'style':'nope'}},'finish/spec.py:149'),
 ('frame-color',{'frame':{'color':'red'}},'finish/spec.py:152'),
 ('frame-weight',{'frame':{'weight':'huge'}},'finish/spec.py:155'),
 ('frame-ratio',{'frame':{'canvas_ratio':'2:1'}},'finish/spec.py:158'),
 ('frame-length',{'frame':{'text':'W'*25}},'finish/spec.py:161'),
 ('frame-flag',{'frame':{'show_logo':'bad'}},'finish/spec.py:164'),
 ('stamp-content',{'stamp':{'content':'nope'}},'finish/spec.py:184'),
 ('stamp-font',{'stamp':{'font':'nope'}},'finish/spec.py:187'),
 ('stamp-color',{'stamp':{'color':'blue'}},'finish/spec.py:190'),
 ('stamp-size',{'stamp':{'size':'giant'}},'finish/spec.py:193'),
 ('stamp-corner',{'stamp':{'corner':'center'}},'finish/spec.py:196'),
 ('stamp-length',{'stamp':{'text':'W'*25}},'finish/spec.py:199'),
 ('stamp-date-syntax',{'stamp':{'date_override':'10/31/2026'}},'finish/spec.py:207'),
 ('stamp-date-invalid',{'stamp':{'date_override':'2026-02-30'}},'finish/spec.py:207'),
 ('stamp-flag',{'stamp':{'enabled':'bad'}},'finish/spec.py:210'),
 ('stamp-format',{'stamp':{'date_format':'yyyy-mm-dd'}},'finish/spec.py:213')]:
 cases.append((name,'PUT',f'/api/photos/{sid}/edit',body,'src/gxr_studio/'+line))
for name,body in [('export-quality-zero',{'quality':0}),('export-quality-over',{'quality':101}),('export-edge-small',{'long_edge':63}),('export-edge-large',{'long_edge':30001})]:
 cases.append((name,'POST',f'/api/photos/{sid}/export',body,'src/gxr_studio/export.py:69' if 'quality' in name else 'src/gxr_studio/export.py:71'))
rows=[]
for name,method,url,body,line in cases:
 r=c.request(method,url,**({'json':body} if body is not None else {}));data=r.json()
 rows.append({'case':name,'method':method,'url':url,'request':body,'status':r.status_code,'response':data,'source':line,'compliant':data.get('message')=='请求无效。请刷新页面后重试。'})
 assert r.status_code==422,(name,r.status_code,data)
(E/'copy-api-r3.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n')
with (E/'COPY_VIOLATIONS-r3.tsv').open('w') as out:
 w=csv.writer(out,delimiter='\t');w.writerow(['文件:行','字符串','不合规原因','复现用例'])
 for row in rows:
  if not row['compliant']:w.writerow([row['source'],row['response'].get('message'),'COPY 3.13-2：界面控件和提交前校验不产生的非法参数，应使用统一主句；原因放 detail',row['case']])
# Inheritance and explicit off remain distinct across a later defaults change.
c.delete(f'/api/photos/{sid}/edit');c.delete(f'/api/photos/{sid}/crop')
def pv():
 r=c.get(f'/api/photos/{sid}/render?stage=final&size=full');assert r.status_code==200,r.text
 im=Image.open(io.BytesIO(r.content));im.load();return list(im.size)
def default(style,text):
 r=c.put('/api/defaults/finish',json={'frame':{'style':style},'stamp':{'enabled':True,'content':'text','font':'sans','text':text}});assert r.status_code==200,r.text
result={}
default('gallery','FIRST');result['inherited']={'edit':c.get(f'/api/photos/{sid}/edit').json(),'wh':pv()}
r=c.put(f'/api/photos/{sid}/edit',json={'frame':{'style':'none'},'stamp':{'enabled':False}});assert r.status_code==200,r.text
result['explicit_off']={'edit':r.json(),'wh':pv()}
default('leica','SECOND');result['off_after_new_defaults']={'edit':c.get(f'/api/photos/{sid}/edit').json(),'wh':pv()}
c.delete(f'/api/photos/{sid}/edit');result['unset_after_new_defaults']={'edit':c.get(f'/api/photos/{sid}/edit').json(),'wh':pv()}
c.put('/api/defaults/finish',json={'frame':{'style':'none'},'stamp':{'enabled':False}})
c.delete(f'/api/photos/{sid}/edit');c.delete(f'/api/photos/{sid}/crop')
(E/'default-states-r3.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
c.close();print(json.dumps({'copy_probes':len(rows),'copy_noncompliant':sum(not r['compliant'] for r in rows),'default_states':{k:v['wh'] for k,v in result.items()}},ensure_ascii=False))
