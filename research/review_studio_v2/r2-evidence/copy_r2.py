"""Re-run the previous AST audit, discard stale line-number findings, inventory frontend literals."""
from pathlib import Path
import ast,csv,json,re
import copy_audit as old
HERE=Path(__file__).resolve().parent
old.MANUAL={}
old.main()
backend=list(csv.DictReader((HERE/'COPY_VIOLATIONS.tsv').open(),delimiter='\t'))
# Source-only frontend string inventory, comments excluded. Runtime findings are checked separately.
TOKEN=re.compile(r'//[^\n]*|/\*[\s\S]*?\*/|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|`(?:\\.|[^`\\])*`')
frontend=[];flags=[]
for p in sorted((old.STUDIO/'web').rglob('*.js')):
 text=p.read_text()
 for m in TOKEN.finditer(text):
  s=m.group()
  if s.startswith('//') or s.startswith('/*') or not re.search('[\u4e00-\u9fff]',s):continue
  row={'file':str(p.relative_to(old.STUDIO)),'line':text.count('\n',0,m.start())+1,'string':s}
  frontend.append(row)
  bad=[word for word in old.FORBIDDEN if word in s]
  if bad:flags.append({**row,'reason':'禁用术语：'+'、'.join(bad)})
# Inspect Python status fields separately from errors, and ignore detail/debug strings.
statuses=[]
for p in sorted((old.STUDIO/'src/gxr_studio').rglob('*.py')):
 text=p.read_text();tree=ast.parse(text)
 for n in ast.walk(tree):
  if not isinstance(n,ast.Dict):continue
  for k,v in zip(n.keys,n.values):
   if isinstance(k,ast.Constant) and k.value in ('message','reason','note','label','render_text','warning'):
    s=ast.get_source_segment(text,v) or ''
    if not re.search('[\u4e00-\u9fff]',s):continue
    statuses.append({'file':str(p.relative_to(old.STUDIO)),'line':v.lineno,'field':k.value,'string':s})
    bad=[w for w in old.FORBIDDEN if w in s]
    if bad:backend.append({'文件:行':f'{p.relative_to(old.STUDIO)}:{v.lineno}','字符串':s,'不合规原因':'禁用术语：'+'、'.join(bad)})
(HERE/'copy-r2-inventory.json').write_text(json.dumps({'frontend':frontend,'statuses':statuses},ensure_ascii=False,indent=2)+'\n')
(HERE/'copy-r2.json').write_text(json.dumps({'backend_candidates':backend,'frontend_candidates':flags,'frontend_literals':len(frontend),'status_fields':len(statuses)},ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'backend_candidates':backend,'frontend_candidates':flags,'frontend_literals':len(frontend),'status_fields':len(statuses)},ensure_ascii=False,indent=2))
