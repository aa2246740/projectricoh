"""Check saved valid rectangles against every original mask pixel, not corner colors."""
from pathlib import Path
import json,sys
import numpy as np
STUDIO=Path('/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/studio')
sys.path.insert(0,str(STUDIO/'src'))
from gxr_studio.finish.geometry import warp,normalized_valid_rect,clamp_norm_rect,output_size
from gxr_studio.finish.spec import Geometry
rows=[]
for w,h in [(640,480),(1600,1200)]:
 for desc,g in [('straighten15',Geometry(straighten=15)),('vertical80',Geometry(vertical=80)),('horizontal80',Geometry(horizontal=80)),('distortion70',Geometry(distortion=70)),('combined',Geometry(straighten=12,vertical=60,horizontal=-40,distortion=30))]:
  rgb,v=warp(np.full((h,w,3),100,np.uint8),g)
  rect=normalized_valid_rect(v)
  x,y,bw,bh=[round(a*b) for a,b in zip(rect,(v.shape[1],v.shape[0],v.shape[1],v.shape[0]))]
  invalid=int((~v[y:y+bh,x:x+bw]).sum())
  clamped=clamp_norm_rect(v,rect)
  row={'source_wh':[w,h],'geometry':desc,'api_canvas_wh':output_size(w,h,g),'actual_canvas_wh':[v.shape[1],v.shape[0]],'initial_saved_rect':rect,'invalid_pixels_in_saved_rect':invalid,'actual_final_rect':clamped,'same_rect':rect==clamped}
  rows.append(row)
  print(json.dumps(row),flush=True)
Path(__file__).with_name('geometry-r2.json').write_text(json.dumps(rows,indent=2)+'\n')
