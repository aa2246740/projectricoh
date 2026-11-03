"""Generate studio/src/gxr_studio/lut/{cube,spaces,colorimetry}.py and PROVENANCE.json from the research sources.

spaces.py is a byte-identical copy. cube.py is the research file with the `guard` import and the two guarded
file helpers replaced (listed under "edits"). colorimetry.py consists only of source text of AST nodes of
research/color_table_fit/dng_scene.py (constants, colour helpers, DngColour, white_from_neutral) in original order.

    python3 research/studio_lut_s8a/tools/extract_lut.py
"""
import ast
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'studio/src/gxr_studio/lut'
MANIFEST = ROOT / 'research/studio_design/reuse_manifest.tsv'
SRC = {
    'cube': 'research/lut_convert/cube.py',
    'spaces': 'research/lut_convert/spaces.py',
    'dng_scene': 'research/color_table_fit/dng_scene.py',
}
# not in reuse_manifest.tsv; pinned here (same value the E0 extraction used for its dng_scene-derived files)
EXTRA_SHA = {'research/color_table_fit/dng_scene.py': 'f0e8dd88baed2f6894b2427de7d7342ce37b2105716b2c47111d49ecfda5f59d'}

COLOUR_CONSTANTS = ('D50_XY', 'D65_XY', 'BRADFORD', 'ILLUMINANT_K', 'ROBERTSON', 'TINT_SCALE')
COLOUR_FUNCS = ('xy_to_xyz', 'xyz_to_xy', 'bradford', 'xy_to_cct', 'white_from_neutral')
COLOUR_CLASSES = ('DngColour',)


def sha(rel):
    return hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()


def check():
    rows = [l.split('\t') for l in MANIFEST.read_text().splitlines()[1:]]
    table = {r[1]: r[6] for r in rows}
    table.update(EXTRA_SHA)
    for rel in SRC.values():
        if sha(rel) != table.get(rel):
            raise SystemExit(f'{rel}: SHA-256 does not match the pinned value')


def segments(rel, wanted):
    text = (ROOT / rel).read_text()
    lines = text.splitlines()
    tree = ast.parse(text)
    out = []
    for node in tree.body:
        name = None
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            name = node.name
        elif isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
            name = node.targets[0].id
        if name in wanted:
            start = node.lineno - 1
            # keep the comment lines directly above a constant (they document the source of the numbers)
            while start > 0 and lines[start - 1].startswith('#'):
                start -= 1
            out.append((name, '\n'.join(lines[start:node.end_lineno])))
    got = {n for n, _ in out}
    if got != set(wanted):
        raise SystemExit(f'missing in {rel}: {sorted(set(wanted) - got)}')
    return [t for _, t in out]


def cube_text():
    text = (ROOT / SRC['cube']).read_text()
    edits = []
    head = 'from guard import input_path, sha\n'
    assert head in text
    text = text.replace(head, 'import hashlib\nfrom pathlib import Path\n')
    edits.append('guard import replaced by hashlib/pathlib')
    old_read = text[text.index('    @classmethod\n    def read(cls, path):'):text.index('    @classmethod\n    def parse')]
    new_read = ('    @classmethod\n    def read(cls, path):\n'
                '        p = Path(path)\n'
                '        if not p.is_file() or p.stat().st_size > MAX_BYTES:\n'
                "            raise ValueError('cube 文件不存在或超过 64 MiB')\n"
                '        raw = p.read_bytes()\n'
                "        return cls.parse(raw.decode('utf-8-sig'), hashlib.sha256(raw).hexdigest())\n\n")
    text = text.replace(old_read, new_read)
    edits.append('Cube.read: no guard.input_path/sha; sha256 of the bytes read')
    i = text.index('def write_cube(')
    text = text[:i] + (
        'def write_cube(path, fun, size=33, title=\'synthetic\'):\n'
        '    """Test fixture writer."""\n'
        '    p = Path(path)\n'
        '    p.parent.mkdir(parents=True, exist_ok=True)\n'
        '    a = np.linspace(0, 1, size)\n'
        '    b, g, r = np.meshgrid(a, a, a, indexing=\'ij\')\n'
        '    y = fun(np.stack([r, g, b], axis=-1).reshape(-1, 3))\n'
        "    with p.open('w') as f:\n"
        '        f.write(f\'TITLE "{title}"\\nLUT_3D_SIZE {size}\\n\')\n'
        "        np.savetxt(f, y, fmt='%.10f')\n")
    edits.append('write_cube: no guard.output_path fence')
    return text, edits


def main():
    check()
    OUT.mkdir(parents=True, exist_ok=True)
    cube, cube_edits = cube_text()
    (OUT / 'cube.py').write_text(cube)
    (OUT / 'spaces.py').write_bytes((ROOT / SRC['spaces']).read_bytes())
    header = ('"""DNG colorimetry subset (camera -> XYZ per DNG 1.7 ch. 6) used to put scene light under a log LUT.\n\n'
              'Source: research/color_table_fit/dng_scene.py\n'
              f'Source SHA-256: {EXTRA_SHA[SRC["dng_scene"]]}\n'
              'Verbatim AST segments only (see research/studio_lut_s8a/tools/extract_lut.py).\n"""\n'
              'import math\n\nimport numpy as np\n\n\n')
    parts = (segments(SRC['dng_scene'], COLOUR_CONSTANTS) + segments(SRC['dng_scene'], COLOUR_FUNCS)
             + segments(SRC['dng_scene'], COLOUR_CLASSES))
    (OUT / 'colorimetry.py').write_text(header + '\n\n\n'.join(parts) + '\n')
    prov = {
        'schema': 'gxr-studio/lut-provenance/1',
        'files': {
            'cube.py': {'source': SRC['cube'], 'source_sha256': sha(SRC['cube']), 'kind': 'copy with edits',
                        'edits': cube_edits},
            'spaces.py': {'source': SRC['spaces'], 'source_sha256': sha(SRC['spaces']), 'kind': 'byte-identical copy'},
            'colorimetry.py': {'source': SRC['dng_scene'], 'source_sha256': sha(SRC['dng_scene']),
                               'kind': 'verbatim AST segments: ' + ', '.join(
                                   COLOUR_CONSTANTS + COLOUR_FUNCS + COLOUR_CLASSES)},
        },
        'generated_by': 'research/studio_lut_s8a/tools/extract_lut.py',
    }
    (OUT / 'PROVENANCE.json').write_text(json.dumps(prov, indent=2, ensure_ascii=False) + '\n')
    print('wrote', OUT)


if __name__ == '__main__':
    main()
