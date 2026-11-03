"""Account for every provided corpus without promoting nondefault or other-model data."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import runtime as rt
from runtime import np
from collections import Counter,defaultdict
import json


def main():
    rt.module('common','research/closed_loop/common.py')
    tiff=rt.module('ceiling_catalog_tiff','research/gr_incamera_dev/tiff_io.py')
    inventory=rt.read(rt.LOCAL/'inventory.json')
    frozen=json.loads((rt.LOCAL/'inputs.json').read_text())
    rows=[];summaries=[];seen={};duplicates=[]
    for corpus in inventory[:6]:
        root=rt.ROOT/corpus['folder'];count=Counter();errors=[]
        for path in sorted(root.rglob('*')):
            if not path.is_file() or path.suffix.lower()!='.dng':continue
            key=str(path.relative_to(rt.ROOT));digest=frozen[key]
            if digest in seen:
                duplicates.append(dict(source=key,same_as=seen[digest],sha256=digest))
                continue
            seen[digest]=key
            try:
                t=tiff.Tiff(rt.inp(path).read_bytes());tags=t.tags()
                model=t.scalar(t.root,272,'unknown').strip();fw=t.scalar(t.root,305,'unknown').strip()
                iso=[]
                for node in t.ifds:
                    if 34855 in node.entries:iso=node.entries[34855].value
                cm=np.array(tags.get(50721,[]));fm=50964 in tags or 50965 in tags
                raw_digest=rt.hashlib.sha256()
                for segment in t.segments(t.raw):
                    raw_digest.update(t.data[segment['offset']:segment['offset']+segment['capacity']])
                count[model]+=1
                rows.append(dict(source=key,sha256=digest,model=model,firmware=fw,iso=iso,
                                 forward_matrix=fm,color_matrix_shape=cm.shape,
                                 raw_stream_sha256=raw_digest.hexdigest(),
                                 color_matrix_signature=rt.hashlib.sha256(cm.tobytes()).hexdigest(),
                                 baseline_exposure=tags.get(50730,[0]),
                                 raw_bits=tags.get(258),source_read_only=True))
            except (ValueError,KeyError,AssertionError) as exc:
                errors.append(dict(source=key,error=str(exc),excluded_from_quantitative_use=True))
        summaries.append(dict(folder=corpus['folder'],unique_DNG_models=dict(count),parse_errors=errors))
    role_map={
      '2026-10-25-gr4-wechat':'four bands Std/Posi define current target; ten Other Std images are natural holdout; nondefault Nega and BB remain setting/clipping diagnostics',
      '2026-10-25-gr4-wechat-nega-redo':'default Negative and same-RAW Std/Posi complete the paired target and prove Positive byte-equivalence',
      '2026-10-22-gr4hdf-screenchart':'independent photographed screen; historical target-consistency and coverage test, not physical cross-sensor truth',
      '2026-10-21-webpairs':'two GR IV Positive real scenes are frozen natural holdouts; GR III/IIIx are model-generation controls, not GR IV truth',
      '2026-10-21-evalsets':'GR III same-RAW Std/Posi/Nega and IIIx chart are controls for style identity, WB, crop and model mismatch',
      '2026-10-19':'GR IV/HDF natural Std/Posi/Nega validate normalized RAW functions; original GR IV template anchors matrices; other styles support shared radial/DR diagnostics; GR 2013 is an older-generation control',
    }
    rt.dump('materials/catalog.json',dict(corpora=summaries,unique_raws=rows,duplicates=duplicates,roles=role_map,
                    untrusted_inputs_executed=False,other_model_pixels_in_GRIV_target=False))
    # Preserve all diagnostics of the originally returned nondefault Negative and BB.
    source=rt.read('research/gr4_dense_returns_r1/local/diagnostic_summary.json')
    rt.dump('materials/nondefault_diagnostics.json',source)
    rt.dump('materials/historical_consistency.json',dict(
        positive=rt.read('research/gr4_dense_returns_r1/local/target/historical_consistency.json'),
        negative=rt.read('research/gr4_nega_returns_r1/local/target/historical_consistency.json')))
    print('catalog unique DNG',len(rows),'duplicates',len(duplicates),'models',dict(Counter(x['model'] for x in rows)),flush=True)


if __name__=='__main__':main()
