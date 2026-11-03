"""Output-quantisation sensitivity for the only admitted independent MOUNT row."""
import itertools
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import runtime as rt
from probe2_refit import Flow,OUT
from mount_bracket_sensitivity import phase_output
from entry_codec import predict as original_predict


def main():
    index=32;flow=Flow(index);root=OUT/'fits'/f'{index:02d}'
    record=(root/'exact.record552').read_bytes();groups={}
    for group in ('synthetic','photo_iso200','photo_new7_RAW_diagnostic'):
        data=flow.groups[group]
        anchor=original_predict(flow.anchor,data['x'],2,round_output=False)
        candidate=flow.model.predict(record,data['x'],round_output=False)
        values=[]
        for order in ('YCbCr8_then_RGB8','RGB8_then_YCbCr8'):
            for phase in itertools.product((0.,.5),repeat=3):
                a=rt.score(data['base'],phase_output(anchor,phase,order),data['want'])
                b=rt.score(data['base'],phase_output(candidate,phase,order),data['want'])
                gain=None if a['similarity_percent'] is None else b['similarity_percent']-a['similarity_percent']
                values.append(dict(order=order,phase=phase,anchor=a,candidate=b,gain_pp=gain))
        gains=[v['gain_pp'] for v in values if v['gain_pp'] is not None]
        groups[group]=dict(branches=values,gain_min_pp=min(gains) if gains else None,
            gain_max_pp=max(gains) if gains else None,hardware_quantisation_phase_identified=False)
    rt.dump(OUT/'06_output_phase_sensitivity.json',dict(label='电脑预测，输出取整敏感性，不能代表ISP算法',
        index=index,record_sha256=rt.sha(root/'exact.record552'),groups=groups,
        no_JPEG_DCT_or_IDCT_simulation=True,parameter_selection_not_changed=True))
    print('PROBE2 06 PHASE',[(g,v['gain_min_pp'],v['gain_max_pp']) for g,v in groups.items()],flush=True)


if __name__=='__main__':main()
