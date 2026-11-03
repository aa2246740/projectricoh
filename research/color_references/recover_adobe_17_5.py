#!/usr/bin/env python3
"""Assemble an inert official package from hashed prefixes and small ranges.

Each new HTTP request uses a fresh directory and an exact range <=8 MiB.
Early EOF never counts as a complete transfer. The final archive is not run.
"""
import argparse,concurrent.futures,hashlib,json,sys
from pathlib import Path
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE))
from fetch_source import fetch
URL='https://download.adobe.com/pub/adobe/dng/mac/DNGConverter_17_5.pkg'
TOTAL=1831036849
DOWNLOADS=Path('/tmp/gxr_color_refs/downloads')

def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        while chunk:=f.read(1024*1024):h.update(chunk)
    return h.hexdigest()

def copy_range(src,out,start,end,source_start=0):
    with src.open('rb') as f:
        f.seek(start-source_start);out.seek(start)
        remaining=end-start
        while remaining:
            chunk=f.read(min(1024*1024,remaining))
            if not chunk:raise ValueError('Source interval ends early')
            out.write(chunk);remaining-=len(chunk)

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--prefix',default='adobe175_recovery')
    parser.add_argument('--destination',type=Path,default=Path('/tmp/gxr_color_refs/extracted/adobe175_download_assembly'))
    a=parser.parse_args();dest=a.destination
    if not dest.is_relative_to(Path('/tmp/gxr_color_refs')):raise ValueError('Scratch destination required')
    dest.mkdir(parents=True,exist_ok=True)
    previous=[DOWNLOADS/'adobe_converter_17_5/receipt.json']+sorted(DOWNLOADS.glob('adobe175_part_*/receipt.json'))
    sources=[]
    for receipt in previous:
        if not receipt.exists():continue
        r=json.loads(receipt.read_text());p=Path(r['local_path']);count=p.stat().st_size
        assert r['url']==URL and count==r['bytes'] and sha(p)==r.get('sha256',r.get('partial_sha256'))
        if not count:continue
        start=r.get('requested_byte_range',[0])[0]
        sources.append({'path_scratch':str(p),'receipt':str(receipt),'start':start,'end':start+count,
            'sha256':sha(p),'from_incomplete_transfer':r['status']!='downloaded'})
    sources.sort(key=lambda s:(s['start'],-s['end']))
    covered=[]
    for s in sources:
        if covered and s['start']<=covered[-1][1]:covered[-1][1]=max(covered[-1][1],s['end'])
        else:covered.append([s['start'],s['end']])
    holes=[];cursor=0
    for start,end in covered:
        if cursor<start:holes.append((cursor,start))
        cursor=max(cursor,end)
    if cursor<TOTAL:holes.append((cursor,TOTAL))
    gaps=[]
    for start,end in holes:
        for x in range(start,end,8*1024*1024):gaps.append((x,min(end,x+8*1024*1024)))
    print(json.dumps({'new_ranges':len(gaps),'new_bytes':sum(y-x for x,y in gaps),'reused_sources':len(sources)}),flush=True)
    def gap_job(index,interval):
        start,end=interval
        for attempt in range(1,4):
            try:
                p=fetch(f'{a.prefix}_{index:03}_try{attempt}',URL,'part.bin',
                    'Adobe proprietary; inert exact range, no installation or original redistribution',f'{start}:{end-1}',quiet=True)
                return {'path_scratch':str(p),'receipt':str(p.parent/'receipt.json'),'start':start,'end':end,'sha256':sha(p),'from_incomplete_transfer':False}
            except Exception:
                if attempt==3:raise
    with (dest/'converter.pkg').open('x+b') as out:
        out.truncate(TOTAL)
        written=[]
        for s in sources:
            p=Path(s['path_scratch'])
            for x,y in written:
                lo,hi=max(x,s['start']),min(y,s['end'])
                if lo<hi:
                    with p.open('rb') as f:
                        f.seek(lo-s['start']);out.seek(lo)
                        remaining=hi-lo
                        while remaining:
                            n=min(1024*1024,remaining)
                            assert f.read(n)==out.read(n),'Overlapping official responses disagree'
                            remaining-=n
            copy_range(p,out,s['start'],s['end'],s['start']);written.append((s['start'],s['end']))
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            futures=[pool.submit(gap_job,i,g) for i,g in enumerate(gaps)]
            for done,future in enumerate(concurrent.futures.as_completed(futures),1):
                s=future.result();copy_range(Path(s['path_scratch']),out,s['start'],s['end'],s['start']);sources.append(s)
                if done%10==0 or done==len(gaps):print(json.dumps({'ranges_completed':done,'ranges_total':len(gaps)}),flush=True)
    digest=sha(dest/'converter.pkg')
    manifest={'url':URL,'path_scratch':str(dest/'converter.pkg'),'bytes':TOTAL,'sha256':digest,
        'assembly':'Reuse verified prefixes of interrupted transfers; verify overlaps; fill every uncovered byte with exact <=8 MiB HTTP ranges',
        'parts':sources,'re_fetch_instruction':'python3 -I research/color_references/recover_adobe_17_5.py --prefix UNIQUE_NEW_PREFIX --destination /tmp/gxr_color_refs/extracted/UNIQUE_NEW_FOLDER',
        'installed':False,'downloaded_code_executed':False}
    (dest/'assembly.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps({'assembled':TOTAL,'sha256':digest}),flush=True)

if __name__=='__main__':main()
