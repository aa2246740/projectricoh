"""Sensitivity to candidate-library knowledge; no fitting or threshold tuning."""
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import infer as i
c=i.c


def main():
    dats={key:i.store.entries_from_dat((c.ROOT/rel).read_bytes()) for key,rel in i.DAT.items()}
    look_rel='firmware/package_v39_g153_test/local/SD_ROOT/GXRCE.DAT'
    look_dat,look_entries=i.store.entries_from_dat((c.ROOT/look_rel).read_bytes())
    extra={f'look:{look.name}':look.entry for look in look_dat.looks if look.unit_mask&4}
    out=[]
    for row in i.labels():
        if row['group']!='chart-g150':continue
        folder=c.ROOT/row['folder'];dng=i.Dng(folder/(row['file']+'.DNG'))
        with i.Image.open(folder/(row['file']+'.JPG')) as im:rgb=i.np.asarray(im.convert('RGB'))
        codes,observed,cells,_=i.sampling(dng,rgb)
        model=i.make_model(200,dats['g150'][1][(0,4)])
        expected=i.candidates(dats['g150'][1],2,dats['g150'][0])
        wrong=i.candidates(dats['g137'][1],2,dats['g137'][0])
        expanded={**expected,**extra}
        results={name:i.classify(model,bank,codes,observed,cells) for name,bank in
                 [('expected-g150',expected),('wrong-g137',wrong),('extra-current-looks',expanded)]}
        out.append(dict(file=row['file'],truth=row['truth'],label_evidence=row['label_evidence'],results=results))
        dng.release()
    summary={}
    for name in out[0]['results']:
        results=[(r['truth'],r['results'][name]) for r in out]
        summary[name]=dict(n=len(results),top1_correct=sum(truth in result['aliases'] for truth,result in results),
                          supported=sum(result['quality']=='supported' for truth,result in results),
                          supported_wrong=sum(result['quality']=='supported' and truth not in result['aliases'] for truth,result in results))
    c.dump('inference_limits.json',dict(summary=summary,frames=out,
          warning='conditional labels; looks are additional candidates, not new ground-truth examples',
          look_source=look_rel,extra_candidate_names=sorted(extra)))
    c.finish('inference-limits')
    print(json.dumps(summary))


if __name__=='__main__':main()
