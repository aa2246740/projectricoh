"""Extract final gate IR without normalizing away any computation."""
from pathlib import Path
import difflib,re
OUT=Path(__file__).resolve().parent
def normalize(s):
    names={}
    def iv(m):
        if m[0] not in names:names[m[0]]='IV'+str(len(names))
        return names[m[0]]
    s=re.sub(r'ivtmp\.\d+',iv,s)
    s=re.sub(r'(?:\.lto_priv\.\d+)+','',s)
    s=re.sub(r'v\.\d+','v.LOCAL',s)
    return s.splitlines()[1:]
def main():
    streams={}
    for g,d in ((116,'compiler116'),(117,'compiler')):
        text=next((OUT/d).glob('*.optimized')).read_text();start=text.index(';; Function gate_validate.constprop');end=text.find(';; Function ',start+5)
        part=text[start:end];(OUT/f'gate{g}.gimple').write_text(part);streams[g]=part
    for n,fn in (('gate-gimple.patch',lambda s:s.splitlines()),('gate-gimple-normalized.patch',normalize)):
        patch=difflib.unified_diff(fn(streams[116]),fn(streams[117]),lineterm='')
        (OUT/n).write_text('\n'.join(patch)+'\n')
    print('gate GIMPLE extracted; only identity names normalized, all arithmetic retained')
if __name__=='__main__':main()
