"""Summarize downloaded logs without contacting GitHub."""
from pathlib import Path
import collections,json,re
r=Path(__file__).resolve().parent
def parse(name):
 text=(r/(name+'.log')).read_text();cases={};skips=[]
 for line in text.splitlines():
  match=re.search(r'(tests[\\/].+?) (PASSED|SKIPPED|FAILED|ERROR)\b',line)
  if match:
   key=match[1].replace('\\\\','/').replace('\\','/')
   key=re.sub(r'\\u([0-9a-fA-F]{4})',lambda m:chr(int(m[1],16)),key)
   if 'test_render_equals_the_research_model_pixel_for_pixel[' in key:key=key[:key.index('[')]+'[runtime-python]'
   assert key not in cases,key
   cases[key]=match[2]
  match=re.search(r'SKIPPED \[(\d+)\] (.+?):(\d+): (.+)$',line)
  if match:skips.append({'count':int(match[1]),'file':match[2],'line':int(match[3]),'reason':re.sub(r'\\u([0-9a-fA-F]{4})',lambda m:chr(int(m[1],16)),match[4])})
 totals=[line.split('\t',2)[-1] for line in text.splitlines() if re.search(r'[0-9]+ passed(?:, [0-9]+ skipped)?|collected [0-9]+ items',line)]
 return {'cases':cases,'counts':dict(collections.Counter(cases.values())),'skip_reasons':skips,'totals':totals,'case_record_count':len(cases),'case_records_complete':name in ['debug-windows','debug-macos','pr-windows','pr-macos','push-windows']}
results={name:parse(name) for name in ['debug-windows','debug-macos','debug-check','debug-probes','pr-windows','pr-macos','pr-linux','push-windows']}
for name in ['debug-windows','debug-macos','pr-windows','pr-macos','push-windows']:assert len(results[name]['cases'])==1731 and not set(results[name]['counts'])-{'PASSED','SKIPPED'}
win,mac=results['pr-windows']['cases'],results['pr-macos']['cases'];assert set(win)==set(mac)
comparison={'common_skipped':[k for k in win if win[k]==mac[k]=='SKIPPED'],'different_statuses':[{'case':k,'windows':win[k],'macos':mac[k]} for k in sorted(win) if win[k]!=mac[k]],'windows_counts':results['pr-windows']['counts'],'macos_counts':results['pr-macos']['counts']}
assert len(comparison['common_skipped'])==697
(r/'ci-all-tests.json').write_text(json.dumps(results,indent=2,ensure_ascii=False)+'\n');(r/'ci-final-comparison.json').write_text(json.dumps(comparison,indent=2,ensure_ascii=False)+'\n')
for name,row in results.items():print(name,row['counts'],row['totals'][-2:])
print('common skips',len(comparison['common_skipped']))
