"""Group OCR observations by the page number printed in each video frame."""
from pathlib import Path
from collections import Counter,defaultdict
import argparse,json,re

HERE=Path(__file__).resolve().parent
TMP=Path('/Volumes/Workspace/Scratch/tmp/projectricoh/diag-mount-decode-r1')
HEADER=re.compile(r'B[O0]{2}\s*([0-9A-F]{4})\s*/\s*([0-9A-F]{4})')
HEX=re.compile(r'[0-9A-F]{8}')
CHARMAP=str.maketrans({'O':'0','О':'0','Е':'E','С':'C','А':'A','В':'B'})
def normalize(text):return text.upper().replace(' ','').translate(CHARMAP)

def parse(record):
    lines=sorted(record.get('lines',[]),key=lambda x:-x['y'])
    titles=[]
    for line in lines:
        for candidate in line['candidates']:
            found=HEADER.search(candidate['text'].upper())
            if found:titles.append((int(found[1],16),int(found[2],16),line))
    if not titles:return None
    page,total,header=titles[0]
    if total!=37 or page>=37:return None
    count=4 if page==36 else 7
    words=[]; confidences=[]; raw=[]
    for line in lines:
        if line['y']>=header['y']:continue
        if not 0.035<=line['x']<=0.65:continue
        candidate=next((c for c in line['candidates'] if HEX.fullmatch(normalize(c['text']))),None)
        if candidate:
            words.append(normalize(candidate['text']));confidences.append(candidate['confidence'])
        raw.append(line['candidates'][0]['text'])
    return dict(page=page,total=total,words=words,complete=len(words)==count,
                confidence=sum(confidences)/len(confidences) if confidences else 0,
                raw_lines=raw,frame=int(Path(record['file']).stem.split('-')[-1]),file=record['file'])

def main():
    p=argparse.ArgumentParser();p.add_argument('video',choices=['IMG_6293','IMG_6294']);a=p.parse_args()
    groups=defaultdict(list);all_records=[]
    path=HERE/(a.video+'-ocr.jsonl')
    for line in path.read_text().splitlines():
        record=parse(json.loads(line))
        if record:groups[record['page']].append(record);all_records.append(record)
    chosen={};disagreement={};missing=[]
    for page in range(37):
        candidates=[x for x in groups[page] if x['complete']]
        if not candidates:missing.append(f'{page:04X}');continue
        votes=Counter(tuple(x['words']) for x in candidates)
        winner,count=votes.most_common(1)[0]
        supporters=[x for x in candidates if tuple(x['words'])==winner]
        center=sum(x['frame'] for x in supporters)/len(supporters)
        selected=max(supporters,key=lambda x:(x['confidence'],-abs(x['frame']-center)))
        selected=dict(selected,votes=count,candidates=len(candidates))
        chosen[f'{page:04X}']=selected
        if len(votes)>1:disagreement[f'{page:04X}']=[dict(words=list(k),count=v) for k,v in votes.most_common()]
    manual_path=HERE/'manual-review.json'
    manual=json.loads(manual_path.read_text()).get(a.video,{}) if manual_path.exists() else {}
    for page,override in manual.items():
        chosen[page].update(override)
        chosen[page]['file']=str(TMP/a.video/('frame-%05d.jpg'%override['frame']))
        chosen[page]['manually_reviewed']=True
    obj=dict(video=a.video,missing=missing,chosen=chosen,disagreement=disagreement,observations=all_records)
    (HERE/(a.video+'-groups.json')).write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(dict(video=a.video,covered=len(chosen),missing=missing,disagreement=disagreement),ensure_ascii=False))
    if not missing:
        rows=[]
        for page in range(37):
            rows.append(f'BOO {page:04X}/0025');rows.extend(chosen[f'{page:04X}']['words'])
            if page==36:rows.extend(['END BOOT','','DISP:new set'])
        (HERE/(a.video+'-pages.txt')).write_text('\n'.join(rows)+'\n')

if __name__=='__main__':main()
