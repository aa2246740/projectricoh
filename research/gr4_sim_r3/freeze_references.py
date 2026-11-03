"""Match methodological references against the earlier read-only review ledger."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import runtime as rt


def main():
    prior = {r['path']: r['sha256'] for r in rt.read('research/gr4_repos_review_r1/local/inputs.json')}
    names = [
        'research/gr_complete_pipeline/arm_color_math_check.py',
        'research/gr_complete_pipeline/arm_color_extract.py',
        'research/gr_complete_pipeline/arm_gamma_model.py',
        'research/gr_complete_pipeline/arm_gamma_export.py',
        'research/gr_complete_pipeline/arm_color_gr4_calc.asm.txt',
        'research/gr_complete_pipeline/arm_gamma_gr4_builder.asm.txt',
        'artifacts/downloads/gr4-repos/DoYitNow_gr-custom-tool/gr4_editor/codec/gr4_gamma_codec.py',
        'artifacts/downloads/gr4-repos/DoYitNow_gr-custom-tool/gr4_editor/codec/gr4_color_matrix_codec.py',
        'artifacts/downloads/gr4-repos/DoYitNow_gr-custom-tool/gr4_editor/numeric/model.py',
        'artifacts/downloads/gr4-repos/lemonadesaltbagel_GR4-LUTSmith/gr4_lutsmith.py',
        'artifacts/downloads/gr4-repos/Maxwooow_Ricoh-GRMod/core/src/color/camera.ts',
        'artifacts/downloads/gr4-repos/Maxwooow_Ricoh-GRMod/core/src/fw/profile.ts',
    ]
    for name in names:
        assert name in prior
        rt.inp(name, prior[name])
    rt.dump('reference_checks.json', dict(files=len(names), prior_review_digests_all_match=True,
        downloaded_code_executed=False, downloaded_code_copied=False,
        independent_implementation_sources=['own earlier gamma derivation', 'own earlier color matrix derivation'],
        new_region_coordinate_status='explicit hypothesis using native thresholds and selectors'))
    print('Method references match prior review digests.', flush=True)


if __name__ == '__main__': main()
