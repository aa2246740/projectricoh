"""Record the authorized, byte-preserving relocation without recreating old data paths."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import runtime as rt

FILES={
    'look_fits.json':'5b9caf280091ab14c78c0067eb953404a5029850c9c09395aac3ea2b0510f17d',
    'all_fit_parameters.json':'be5d1d91a1bc1cdb20fd96ad250637a4536879a6fba1d9e8a992b5decedcba1a',
    'lumix_fit_parameters.json':'69d5d90c13972f6b731a589d375b33a2511f331fb5a71fe46c2196c98bb6e392'}

def main():
    changes=rt.read(rt.ROOT/'research/fit_data_relocate_r1/evidence/changed-inputs.json')
    paths=[]
    for name,digest in FILES.items():
        old='research/vlog_alchemy_eval/'+name
        new='artifacts/downloads/vlog-alchemy-eval-20261102/'+name
        assert not (rt.ROOT/old).exists()
        assert rt.sha(rt.ROOT/new)==digest
        paths.append(dict(old=old,new=new,sha256=digest,bytes=(rt.ROOT/new).stat().st_size))
    source_changes=[r for r in changes if r['path'].startswith('research/vlog_alchemy_eval/')
                    or r['path']=='research/look_ceiling_r1/prepare.py']
    for row in source_changes:assert rt.sha(rt.ROOT/row['path'])==row['after_sha256']
    rt.dump('relocation_receipt.json',dict(data_paths=paths,authorized_source_changes=source_changes,
        source='Owner/orchestrator instruction during active fits; fit-data-relocate-r1 report and hashes independently read.',
        numerical_data_unchanged=True,old_paths_recreated=False,active_computations_interrupted=False,
        fit_logic_unchanged_is_external_report_claim=True,
        final_reconstruction_against_current_modules_required=True))
    rt.finish('relocation')

if __name__=='__main__':main()
