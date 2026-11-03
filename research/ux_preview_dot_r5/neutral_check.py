"""Validate names and authored text using the existing neutral vocabulary rule."""
from pathlib import Path
import json,sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import ROOT,OUT,TREE,PACKAGE,load,save
words=load(ROOT/'research/review_g119b/neutral_terms.py','quality_final_terms')
issues=[];checked=0
suffixes={'.py','.c','.h','.S','.md','.txt','.json','.jsonl','.tsv','.csv','.asm','.patch','.map','.ld','.stdout','.stderr','.log','.s','.su'}
for root in (TREE,PACKAGE,OUT):
 for p in sorted(root.rglob('*')):
  if words.pattern.search(str(p.relative_to(root))):issues.append(dict(path=str(p.relative_to(root)).encode().hex(),kind='name'))
  if not p.is_file() or p.suffix not in suffixes:continue
  try:text=p.read_text()
  except UnicodeError:continue
  checked+=1
  if words.pattern.search(text):issues.append(dict(path=str(p.relative_to(root)).encode().hex(),root=root.name,kind='text'))
save('neutral-language-check.json',dict(status='PASS' if not issues else 'FAIL',text_files=checked,issues=issues))
print('Neutral-language check',checked,'text files;',len(issues),'issues',flush=True)
assert not issues
