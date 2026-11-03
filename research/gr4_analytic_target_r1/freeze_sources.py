"""Hash read-only methodological sources without importing downloaded code."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import runtime as rt

SOURCES = [
    "research/gr_firmware/REPORT.md",
    "research/gr_complete_pipeline/REPORT.md",
    "research/gr_complete_pipeline/arm_gamma_NOTES.md",
    "research/gr_complete_pipeline/arm_gamma_model.py",
    "research/gr_complete_pipeline/arm_gamma_math_verification.json",
    "research/gr_complete_pipeline/arm_color_analysis.json",
    "research/gr_complete_pipeline/arm_color_math_check.py",
    "research/gr4_dense_returns_r1/REPORT.md",
    "research/gr4_dense_returns_r1/target.py",
    "research/gr4_dense_returns_r1/natural_standard.py",
    "research/gr4_nega_returns_r1/REPORT.md",
    "research/gr4_nega_returns_r1/target.py",
    "research/gr4_modes/REPORT.md",
    "research/gr4_lut_ceiling/REPORT.md",
    "research/gr4_lut_ceiling/style.py",
    "research/gr4_lut_ceiling/isp.py",
    "research/hw_refit_r1/REPORT.md",
    "research/hw_refit_r1/model.py",
    "research/hw_refit_r1/summary.csv",
    "research/hw_refit_r1/best_cases.csv",
    "research/bridge_public_r1/REPORT.md",
    "research/gr_dense_reference/R3_REPORT.md",
    "research/gr_dense_reference/readback_r3.py",
    "research/gr_incamera_dev/analyze.py",
    "research/gr_incamera_dev/predict.py",
    "research/gr_dense_reference/lattice.py",
    "research/gr4_modes/prepare.py",
]
PUBLIC_SOURCES = ["README.md", "FINDINGS.md", "LICENSE", "cube_fit.py", "joint_fit.py", "lab_fit.py", "cca1.py",
    "work/films_v16/refit16.py", "work/v16_plan/hue15.py", "work/ma_probe5/zones.py"]


def main():
    for name in SOURCES:
        rt.inp(name)
    for name in PUBLIC_SOURCES:
        path = rt.inp("artifacts/downloads/gr3-film-mods/repo/" + name)
        path.read_text()  # Data only. runtime blocks execution of downloaded filenames.
    rt.dump("sources.json", dict(methodological_source_count=len(SOURCES) + len(PUBLIC_SOURCES),
        public_commit="04d5d5dd6e85d80089c6200bd0f0de5fff2d658f", downloaded_code_executed=False,
        sources=SOURCES, public_sources=PUBLIC_SOURCES))
    print("read-only source hashes recorded", len(SOURCES) + len(PUBLIC_SOURCES))


if __name__ == "__main__":
    main()
