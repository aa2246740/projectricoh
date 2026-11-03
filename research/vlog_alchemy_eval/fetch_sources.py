"""Save public source documents as data with URLs and hashes."""
import hashlib
import json
import re
from pathlib import Path
import urllib.request
from datetime import datetime,timezone

ROOT=Path('/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh')
OUT=ROOT/'artifacts/downloads/vlog-alchemy-eval-sources-20261102'
SOURCES={
 'fuji-lut':'https://www.fujifilm-x.com/global/support/download/lut/',
 'fuji-terms':'https://global.fujifilm.com/en/terms',
 'nikon-en':'https://downloadcenter.nikonimglib.com/en/download/sw/258.html',
 'nikon-ja':'https://downloadcenter.nikonimglib.com/ja/download/sw/258.html',
 'nikon-agreement-en':'https://downloadcenter.nikonimglib.com/en/sw/ex_agreement.html',
 'nikon-agreement-ja':'https://downloadcenter.nikonimglib.com/ja/sw/ex_agreement.html',
 'leica-legal':'https://leica-camera.com/en-US/legal-notices',
 'arri-legal':'https://www.arri.com/en/legal',
 'red-ipp2':'https://www.reddigitalcinema.com/download/ipp2-output-presets',
 'red-legal':'https://www.reddigitalcinema.com/legal',
 'red-client-text':'https://www.reddigitalcinema.com/RedSuiteCentric/SCA-Kilimanjaro/javascript/shopping.js?t=1793126227791',
 'red-terms-data':'https://www.reddigitalcinema.com/RedSuiteCentric/SCA-Kilimanjaro/services/TermsAndConditions.Service.ss?tc=US',
 'phocus':'https://www.hasselblad.com/phocus/phocus-for-pc-mac',
 'hncs':'https://www.hasselblad.com/learn/hasselblad-natural-colour-solution/',
}

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    rows=[]
    for key,url in SOURCES.items():
        path=OUT/(key+'.html')
        try:
            if path.exists():
                raw=path.read_bytes()
                final=url
            else:
                req=urllib.request.Request(url,headers={'User-Agent':'GXR-Research/1.0'})
                with urllib.request.urlopen(req,timeout=30) as response:
                    final=response.url
                    raw=response.read(8*1024*1024)
                path.write_bytes(raw)
            row={'name':key,'url':url,'resolved_url':final,'path':str(path.relative_to(ROOT)),
                 'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)}
            if key.startswith('nikon'):
                text=raw.decode('utf-8',errors='replace')
                links=re.findall(r'(?:src|href)=["\']([^"\']+)',text)
                row['agreement_links']=[x for x in links if re.search(r'agree|eula|license|\.js',x,re.I)]
            rows.append(row)
            print(key,len(raw),row.get('agreement_links',[]),flush=True)
        except Exception as e:
            rows.append({'name':key,'url':url,'error':str(e)})
            print(key,str(e),flush=True)
        (OUT/'sources.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n')
    (OUT/'SHA256SUMS').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name+'\n'
        for p in sorted(OUT.iterdir()) if p.is_file() and p.name!='SHA256SUMS'))
    (ROOT/'research/vlog_alchemy_eval/source_documents.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n')

if __name__=='__main__':
    main()
