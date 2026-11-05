"""Collect independently verified weighted controls without importing numerical code."""
import hashlib
import json
from pathlib import Path
import sys

assert sys.flags.isolated
LOCAL=Path(__file__).resolve().parent/'local'


def read(path):return json.loads(Path(path).read_text())
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    summary=read(LOCAL/'summary.json');assert summary['complete']
    records=[]
    for film in summary['films']:
        for unit,position in film['units'].items():
            if not position['weighted']['meets_color_and_overall_budget']:continue
            row=read(LOCAL/'weighted_verification'/f'{film["ordinal"]:02d}'/(unit+'.json'))
            assert row['analysis_sha256']==sha(position['analysis_file'])
            assert row['record_sha256']==sha(row['record_file'])
            assert row['primary_record_sha256']==position['full']['sha256']
            assert row['reference_exact_checked'] and row['quantization_branches']==128
            assert row['runtime_C_flags']['dylib_sha256']==sha(LOCAL/'flags_host.dylib')
            assert row['combined_passes']==sum(b['passes'] for b in row['branches'])
            assert row['robust_optional_model_candidate']==bool(row['unweighted_training_improves_stock04'] and row['combined_passes']==128)
            if row['robust_optional_model_candidate']:assert sha(row['optional_export'])==row['record_sha256']
            records.append(row)
    result=dict(status='COMPLETE_LOCAL_CONTROL_EVALUATION',nominally_eligible=len(records),evaluated=len(records),
        robust_optional_records=sum(r['robust_optional_model_candidate'] for r in records),records=records,
        primary_library_remains_unweighted=True)
    (LOCAL/'weighted_controls_summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print('WEIGHTED COLLECTED',len(records),'evaluations;',result['robust_optional_records'],'robust optional records')


if __name__=='__main__':main()
