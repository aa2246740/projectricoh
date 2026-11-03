from pathlib import Path
from datetime import datetime
from unittest.mock import patch
import json,sys
import numpy as np
from PIL import Image
sys.path.insert(0,'/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/studio/src')
from gxr_studio.finish import stamp
from gxr_studio.finish.spec import StampSpec
E=Path(__file__).resolve().parent; R={'formatted':[],'drawing':[]}
for fmt in ("'yy mm dd",'yy mm dd','yyyy.mm.dd',"mm dd 'yy"):
 for show in (False,True):
  spec=StampSpec(enabled=True,content='date+text',text='ABCDEFGHIJKLMNOPQRSTUVWX',date_format=fmt,show_time=show,font='sans')
  text=stamp.format_stamp(spec,datetime(2026,10,31,14,5),None)
  R['formatted'].append({'format':fmt,'show_time':show,'text':text,'all_24':text.endswith(spec.text)})
original=stamp._draw_text
for name,wh in [('portrait_full',(480,640)),('portrait_thumb',(192,256)),('landscape_thumb',(256,192))]:
 for label,text in [('latin','W'*24),('cjk','上海北京'*6)]:
  spec=StampSpec(enabled=True,content='date+text',date_format='yyyy.mm.dd',show_time=True,text=text,font='sans',glow=False)
  row={'name':name,'kind':label,'wh':wh,'draws':[]}
  def observed(draw,xy,shown,face,fill,kind):
   box=draw.textbbox(xy,shown,font=face)
   row['draws'].append({'text':shown,'box':box,'font_px':face.size,'overflow':box[2]>wh[0] or box[3]>wh[1] or box[0]<0 or box[1]<0})
   return original(draw,xy,shown,face,fill,kind)
  with patch.object(stamp,'_draw_text',observed):
   out=stamp.apply_stamp(np.full((wh[1],wh[0],3),30,np.uint8),spec,datetime(2026,10,31,14,5),None)
  if name=='portrait_thumb':Image.fromarray(out).resize((wh[0]*3,wh[1]*3)).save(E/f'stamp-{label}-thumb-r3.png')
  R['drawing'].append(row)
(E/'stamp-r3.json').write_text(json.dumps(R,ensure_ascii=False,indent=2)+'\n');print(json.dumps(R,ensure_ascii=False))
