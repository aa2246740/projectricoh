"""Execute frozen r3 input and preserve its observations before legacy assertions."""
import json,os,sys,traceback
from pathlib import Path
name=sys.argv[1]
prior=Path(__file__).resolve().parent.parent/'review_studio_gpu_preview_r3'/name
g={'__file__':str(prior),'__name__':'__main__'}
result={'input':str(prior),'error':None}
try:exec(compile(prior.read_text(),str(prior),'exec'),g)
except BaseException as exc:
 result['error']=type(exc).__name__+':'+str(exc)
 traceback.print_exc()
result['observations']=g.get('result')
(Path(os.environ['REVIEW_OUT'])/('original-'+name+'.json')).write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result))
