"""Choose a sharp frame among observations with the verified page text."""
from pathlib import Path
import hashlib,json,subprocess,csv

HERE=Path(__file__).resolve().parent
TMP=Path('/Volumes/Workspace/Scratch/tmp/projectricoh/diag-mount-decode-r1')

def sharpness(file):
    value=subprocess.check_output(['magick',file,'-crop','650x1100+60+160','+repage',
             '-colorspace','Gray','-edge','1','-format','%[standard-deviation]','info:'],text=True)
    return float(value)

def main():
    receipt=[]
    for video in ('IMG_6293','IMG_6294'):
        path=HERE/(video+'-groups.json');groups=json.loads(path.read_text())
        times={x['frame']:x['seconds'] for x in json.loads((HERE/(video+'-timestamps.json')).read_text())}
        for page,chosen in groups['chosen'].items():
            observations=[o for o in groups['observations'] if o['page']==int(page,16) and o['words']==chosen['words'] and o['complete']]
            if chosen.get('manually_reviewed'):
                observations=[chosen]
            if not observations:
                observations=[chosen]
            matching_candidates=len(observations)
            scored=[]
            if 'sharpness' in chosen:
                observations=[chosen]
            for item in observations:
                scored.append((sharpness(item['file']),item))
            score,best=max(scored,key=lambda x:x[0])
            chosen.update({key:best[key] for key in ('file','frame','confidence','raw_lines') if key in best})
            chosen['matching_candidates']=matching_candidates
            chosen['sharpness']=score
            chosen['seconds']=times[chosen['frame']]
            chosen['selected_frame_sha256']=hashlib.sha256(Path(chosen['file']).read_bytes()).hexdigest()
            receipt.append(dict(video=video+'.MOV',page=f'BOO {page}/0025',frame=chosen['frame'],
                                seconds=f"{chosen['seconds']:.6f}",sharpness=f'{score:.6f}',
                                candidates=matching_candidates,frame_sha256=chosen['selected_frame_sha256']))
        path.write_text(json.dumps(groups,ensure_ascii=False,indent=2)+'\n')
    with (HERE/'selected-frames.tsv').open('w') as stream:
        writer=csv.DictWriter(stream,fieldnames=receipt[0].keys(),delimiter='\t');writer.writeheader();writer.writerows(receipt)
    for video in ('IMG_6293','IMG_6294'):
        groups=json.loads((HERE/(video+'-groups.json')).read_text())
        tiles=[]
        for page,chosen in groups['chosen'].items():
            tile=TMP/f'{video}-{page}-tile.png';tiles.append(tile)
            subprocess.run(['magick',chosen['file'],'-resize','400x710!',
                            '-gravity','south','-background','white','-splice','0x36',
                            '-fill','black','-font','/System/Library/Fonts/Menlo.ttc','-pointsize','17',
                            '-annotate','+0+8',f"{video} {page} f{chosen['frame']} {chosen['seconds']:.3f}s",str(tile)],check=True)
        for start in range(0,len(tiles),8):
            target=TMP/f'{video}-sheet-{start//8}.png'
            subprocess.run(['magick','montage','-font','/System/Library/Fonts/Menlo.ttc',*[str(p) for p in tiles[start:start+8]],
                            '-tile','4x2','-geometry','+4+4','-background','white',str(target)],check=True)
    print('selected 74 frames; made 10 temporary sheets')

if __name__=='__main__':main()
