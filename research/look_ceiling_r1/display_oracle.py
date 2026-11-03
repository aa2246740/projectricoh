"""Exact declared display-target functions on an existing confirmed Standard JPEG."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import runtime as rt
from runtime import np,ROOT,LOCAL
from PIL import Image,ImageOps

def tetra(table,rgb):
    n=len(table);pos=np.clip(rgb/255,0,1)*(n-1);b=np.minimum(pos.astype(int),n-2)
    f=np.rint((pos-b)*256)/256;order=np.argsort(-f,axis=1,kind='stable');rows=np.arange(len(rgb))
    values=[table[b[:,0],b[:,1],b[:,2]].astype(float)];q=b.copy()
    for j in range(3):
        q[rows,order[:,j]]+=1
        values.append(table[q[:,0],q[:,1],q[:,2]].astype(float))
    fractions=np.take_along_axis(f,order,axis=1)
    out=values[0].copy()
    for j in range(3):out+=fractions[:,j,None]*(values[j+1]-values[j])
    return np.clip(out/256,0,255)

def main():
    (LOCAL/'display_oracle').mkdir(exist_ok=True)
    source=ROOT/'artifacts/card-b-mount/card-b-after-v34c-first-run-20261026T032356Z/root/DCIM/100RICOH/R8051477.JPG'
    with Image.open(source) as im:
        rgb=np.asarray(ImageOps.exif_transpose(im).convert('RGB')).reshape(-1,3)
        take=np.linspace(0,len(rgb)-1,20000).astype(int)
        pixels=rgb[take].astype(float)
    rows=[]
    for meta_path in sorted(LOCAL.glob('target_[0-2][0-9].json')):
        meta=rt.read(meta_path)
        if meta['index']>=27 or meta['input'] not in ('srgb','rec709','gamma24') or meta.get('interpretation')=='scene':continue
        job=dict(path=ROOT/meta['source'],input=meta['input'],output=meta['output'],interpretation=meta.get('interpretation','declared'))
        target=rt.fit_adapter.target_of(job)
        want=target.render(pixels,None)
        tables={}
        scores={}
        for size in (17,33,65):
            grid=np.stack(np.meshgrid(*([np.linspace(0,255,size)]*3),indexing='ij'),axis=-1).reshape(-1,3)
            result=[]
            for start in range(0,len(grid),8192):result.append(target.render(grid[start:start+8192],None))
            table=np.rint(np.clip(np.vstack(result),0,255)*256).astype(np.uint16).reshape(size,size,size,3)
            pred=np.rint(tetra(table,pixels))
            scores[str(size)]=rt.score(pixels,pred,want)
            tables['cube_'+str(size)+'_q8_8']=table
        oracle=rt.score(pixels,np.rint(want),want)
        row=dict(label='电脑预测，真实标准JPEG像素',index=meta['index'],name=meta['name'],
            jpeg=str(source.relative_to(ROOT)),jpeg_sha256=rt.sha(source),n=len(pixels),
            scores=scores,direct_target_precision=oracle,
            target_material_can_be_sampled_without_limit=True,sensor_bridge_required_for_this_display_function=False,
            source_input_interpretation=meta['input'],training_result=False)
        rows.append(row)
        np.savez_compressed(LOCAL/'display_oracle'/f'{meta["index"]:02d}.npz',**tables)
        print(meta['name'],'33cube similarity',scores['33']['similarity_percent'],flush=True)
    rt.dump('display_oracle.json',rows)
    rt.finish('display_oracle')

if __name__=='__main__':main()
