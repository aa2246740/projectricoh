from pathlib import Path
from datetime import datetime
import json,sys
sys.path.insert(0,'/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/studio/src')
from gxr_studio.finish.spec import StampSpec
from gxr_studio.finish.stamp import format_stamp
R=[]
for fmt in ("'yy mm dd",'yyyy.mm.dd'):
 for show in (False,True):
  spec=StampSpec(enabled=True,content='date+text',text='ABCDEFGHIJKLMNOPQRSTUVWX',date_format=fmt,show_time=show)
  got=format_stamp(spec,datetime(2026,10,31,14,5),None)
  R.append({'date_format':fmt,'show_time':show,'input_text':spec.text,'actual':got,'all_24_characters_preserved':got.endswith(spec.text)})
Path(__file__).with_name('text-r2.json').write_text(json.dumps(R,indent=2)+'\n')
print(json.dumps(R,indent=2))
