"""Collect observed results and evaluate the frozen design gate unchanged."""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]

def main():
    data=json.loads((HERE/'delta_audit.json').read_text())
    host=json.loads((HERE/'host/results.json').read_text())
    bridge=json.loads((HERE/'bridge/results.json').read_text())
    rebuilt=json.loads((HERE/'rebuild/results.json').read_text())
    native=json.loads((HERE/'native_flow.json').read_text())
    machine=json.loads((HERE/'packed_machine/results.json').read_text())
    sizes=json.loads((HERE/'extra/sizes.json').read_text())
    assert len(host['reruns'])==279 and all(r['status']=='PASS' for r in host['reruns'])
    assert len(bridge['C_H01_H02'])==96 and len(bridge['native_continuations'])==192
    assert len(machine['cases'])==29
    raw=(ROOT/'firmware/engine_v36_r28/local/staged/SD_ROOT/GXRCE.DAT').read_bytes()
    actual=len(raw);required=512;capacity=65536
    result=dict(verdict='不可以上卡',P0=[],P1=[dict(id='P1-01',reason='frozen design headroom gate was lowered in build115.py',
        design_max_file_bytes=capacity-required,actual_bytes=actual,actual_headroom=capacity-actual,
        design_required_headroom=required,gate_shortfall=actual-(capacity-required),gate_pass=actual<=capacity-required)],
        P2=['P2-01 inherited null-table fallback overclaim','P2-02 inherited count=2 native projection',
            'P2-03 cached B5 neighbour requires per-boot stability; native changing writer unproven'],
        sha256=hashlib.sha256(raw).hexdigest(),host_runs=279,independent_C_units=host['independent_units'],
        real_C_H01_H02_cases=96,C_fed_native_continuations=192,
        prior_native_constructor_cases=len(native['constructor_cases']),native_consumers=len(native['consumers']),
        native_render_iterations=len(native['render']),packed_machine_cases=len(machine['cases']),
        envelope_cases=len(json.loads((HERE/'extra/envelope.json').read_text())),
        independent_rebuild=rebuilt,target_sizes=sizes,
        protected_scope='user frozen inputs and consumed evidence; shared downloads limited to official gxr-151.zip and gxr_vup; decisions.tsv excluded',
        camera_card_USB_network_operations=False,real_runtime_acceptance=False)
    (HERE/'review_summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print('REVIEW COMPLETE: design gate FAIL by',result['P1'][0]['gate_shortfall'],'bytes; host checks passed')

if __name__=='__main__':main()
