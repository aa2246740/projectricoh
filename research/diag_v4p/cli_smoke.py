"""Fresh interpreter entry points for decoded version 7 captures."""
from pathlib import Path
import json,struct,sys,zlib
sys.path.insert(0,str(Path(__file__).resolve().parent))
import scope as s
import native_gate as g
import pages as pg

def main():
    s.enable();folder=s.TMP/'cli';folder.mkdir(exist_ok=True);rows=[]
    dat=s.sha(s.PACKAGE/'GXRCE.DAT');ref=s.HERE/'reference-v7.json';pin=s.sha(ref)
    options=['--dat-sha256',dat,'--reference',ref,'--reference-sha256',pin]
    units=[u for u in ('50mm','28mm','mount') if (s.HERE/'evidence'/('record-'+u+'.bin')).exists()]
    for unit in units:
        raw=s.HERE/'evidence'/('record-'+unit+'.bin');out=s.HERE/'evidence'/('decode-'+unit+'.json')
        p=s.run([sys.executable,'-I','-B',s.HERE/'decode.py',raw,*options,'--output',out],'cli-decode-'+unit,check=False)
        doc=json.loads(out.read_text());assert p.returncode==0 and doc['records_complete'],doc
        q=s.run([sys.executable,'-I','-B',s.HERE/'native_gate.py',out,'--raw',raw,'--raw-sha256',s.sha(raw),*options],'cli-native-'+unit,check=False)
        result=json.loads(q.stdout);assert q.returncode==0 and result['records_complete'],result
        source=raw.read_bytes();size=len(source);count=(size+27)//28;data=source+bytes(count*28-size);lines=[]
        for i in range(count):
            lines.append(f'REC {i:04X}/{count:04X}')
            lines.extend(data[28*i+4*j:28*i+4*j+4].hex().upper() for j in range(7))
        page_text='\n'.join(lines)+'\n';assert pg.parse(page_text,7)==source
        for changed in ('\n'.join(lines[8:])+'\n','\n'.join(lines[:8]+lines)+'\n',page_text.replace('REC 0000/','REC 0001/',1)):
            try:pg.parse(changed,7)
            except ValueError:pass
            else:raise AssertionError('page sequence accepted')
        page_file=folder/(unit+'.txt');page_file.write_text(page_text);rebuilt=folder/(unit+'.bin')
        q=s.run([sys.executable,'-I','-B',s.HERE/'pages.py',page_file,'--version','7','--output',rebuilt],'cli-pages-'+unit,check=False)
        assert q.returncode==0 and rebuilt.read_bytes()==source,q.stdout
        rows.append(dict(name=unit,decode=0,gate=0,raw_sha256=s.sha(raw)))
    for unit in ('28mm','mount'):
        path=s.HERE/'evidence'/('quick-record-'+unit+'.bin')
        if path.exists():
            q=s.run([sys.executable,'-I','-B',s.HERE/'decode.py',path,*options],'cli-quick-'+unit,check=False)
            result=json.loads(q.stdout);assert q.returncode==2 and not result['records_complete'],result
            rows.append(dict(name=unit+'-focused-incomplete',decode=2))
    source=(s.HERE/'evidence/record-50mm.bin').read_bytes()
    for name,raw in (('crc',source[:-1]+bytes([source[-1]^1])),('missing',source[:-4])):
        path=folder/(name+'.bin');path.write_bytes(raw)
        q=s.run([sys.executable,'-I','-B',s.HERE/'decode.py',path,*options],'cli-'+name,check=False)
        result=json.loads(q.stdout);assert q.returncode==2 and not result['records_complete'],result
        rows.append(dict(name=name,decode=2,result=result))
    s.save(s.HERE/'evidence/cli-smoke.json',dict(status='PASS',dat_sha256=dat,commands=rows,model_positive=len(units)))
    print('PASS fresh command entry points',len(rows))
if __name__=='__main__':main()
