#!/usr/bin/env python3
"""Freeze copies of existing extractors, the v2 chain and round-4 safety code."""
import sys
sys.dont_write_bytecode = True
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import ast
import re
from common import ROOT, LOCAL, mount_guard, sha, dump, require, helper


SOURCES = [
    'research/hue_ring/analyze_ring.py', 'research/hue_ring/sector_model.py',
    'research/hue_ring/pilplot.py', 'research/hue_ring/patches.json',
    'research/t1_probe/probe2/calibration_geometry.py',
    'research/stage2d_verification/analyze.py',
    'research/stage2e_verification/analyze_2e.py',
    'research/color_calibration/analyze_capture.py',
    'research/color_table_fit/matrix_model.py', 'research/color_table_fit/fit_sectors.py',
    'research/color_table_fit/dng_scene.py', 'research/fuji_phase2/fit_fuji.py',
    'firmware/stage2j/tools/deep_sources.py', 'firmware/stage2j/tools/make_recipes.py',
    'research/color_references/colour_math.py',
]


def main():
    mount_guard()
    vendor = LOCAL / 'vendor'
    originals = {str(ROOT / s): sha(ROOT / s) for s in SOURCES}
    for rel in SOURCES:
        p = ROOT / rel
        out = vendor / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        if p.suffix == '.json':
            out.write_bytes(p.read_bytes())
            continue
        code = p.read_text()
        code = re.sub(r'^ROOT\s*=.*$', f'ROOT = Path({str(ROOT)!r})', code, flags=re.M)
        # Redirect helper imports to our own copies. Data paths keep the read-only repository root.
        code = re.sub(r'ROOT\s*/\s*([\'\"])([^\'\"]+\.py)\1',
                      lambda m: f'Path({str(vendor / m[2])!r})', code)
        code = re.sub(r'^HUE\s*=.*$', f'HUE = Path({str(vendor / "research/hue_ring")!r})',
                      code, flags=re.M)
        out.write_text(code)
    extracts = [
        ('research/hue_ring/local/calibration_20261020/followup_v2/code/ring_model_v2.py',
         'PreTable', 'pretable.py', 'from scipy.optimize import brentq\n'),
        ('research/color_fit_v2/05_classic_chrome/round4/fit_round4.py',
         'Safety', 'safety.py', ''),
    ]
    for rel, cls, dest, extra in extracts:
        p = ROOT / rel
        originals[str(p)] = sha(p)
        text = p.read_text()
        node = next(n for n in ast.parse(text).body if isinstance(n, ast.ClassDef) and n.name == cls)
        (vendor / dest).write_text('"""Copied verbatim class; see vendor_manifest.json for origin."""\n'
                                  + 'import numpy as np\nimport math\n' + extra
                                  + ast.get_source_segment(text, node) + '\n')
    bwparts = []
    for rel, names in [
        ('research/gr4_modes/core.py', ('_blk', 'blocks')),
        ('research/gr4_modes/gr4io.py', ('dng_tags_for_colour',)),
        ('research/color_table_fit/bw_mix.py', ('blk_any', 'gr4_blocks')),
    ]:
        p = ROOT / rel
        originals[str(p)] = sha(p)
        text = p.read_text()
        for n in ast.parse(text).body:
            if isinstance(n, ast.FunctionDef) and n.name in names:
                bwparts.append(ast.get_source_segment(text, n))
    (vendor / 'bw_helpers.py').write_text('import numpy as np\n' + '\n\n'.join(bwparts) + '\n')
    require(all(sha(p) == h for p, h in originals.items()), '复制过程中源代码变化')
    dump(LOCAL / 'vendor_manifest.json', {'sources_sha256': originals,
         'copies_sha256': {str(p.relative_to(LOCAL)): sha(p) for p in sorted(vendor.rglob('*')) if p.is_file()},
         'adaptation': 'Only ROOT and code-import paths rebound; PreTable and Safety copied verbatim by AST.'})
    for name in ('ar', 'physical', 'dng', 'mm', 'fs', 'src', 'v2', 'safety'):
        helper(name)
    print('冻结辅助代码并导入通过；所有副本在 local/vendor/。')


if __name__ == '__main__':
    main()
