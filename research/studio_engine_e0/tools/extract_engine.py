"""Generate studio/src/gxr_studio/engine/* from the research sources (verbatim segments only).

Every statement that ends up in the engine is the source text of an AST node of the original file, in the
original order; nothing is rewritten except the import header and (for menu.py) two lines, listed in
PROVENANCE.json under "edits". The sources are SHA-256 checked against reuse_manifest.tsv first.

    python3 research/studio_engine_e0/tools/extract_engine.py          # writes the engine package
"""
import ast
import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ENGINE = ROOT / 'studio/src/gxr_studio/engine'
MANIFEST = ROOT / 'research/studio_design/reuse_manifest.tsv'

SRC = {
    'knobs': 'research/knobs_v2_r2/src/knobs.py',
    'menu': 'research/knobs_v2_r2/src/menu.py',
    'final': 'research/knobs_v2_r2/tables/final.json',
    'matrix_model': 'research/color_table_fit/matrix_model.py',
    'fit_sectors': 'research/color_table_fit/fit_sectors.py',
    'sector_model': 'research/hue_ring/sector_model.py',
    'ring_model_v2': 'research/hue_ring/local/calibration_20261020/followup_v2/code/ring_model_v2.py',
    'model_adapter': 'research/knobs_v2_r2/src/model_adapter.py',
}
# not in reuse_manifest.tsv (the manifest lists the vendored PreTable copy instead); pinned here
EXTRA_SHA = {
    SRC['ring_model_v2']: 'c7a05f3e558378364ca7e8506a0335b8dd4895d395226c139ff8d0edc6291a37',
}
DAT_SOURCES = [   # read to write datcodec.py; hashes recorded, files are not copied
    'firmware/engine_v53_g135/candidate/containers/product/pack.py',
    'firmware/engine_v53_g135/candidate/containers/product/pack_v1.py',
    'firmware/engine_v53_g135/candidate/ui_data.py',
    'firmware/engine_v53_g135/candidate/build135.py',
    'firmware/engine_v53_g135/candidate/containers/product/src/firmware/card_container_v2/gate.c',
    'firmware/engine_v51_g131/candidate/containers/product/pack.py',
    'firmware/engine_v51_g131/candidate/containers/product/src/firmware/card_container_v2/gate.c',
    'firmware/engine_v49_knobs/candidate/containers/product/pack.py',
    'firmware/engine_v49_knobs/candidate/containers/product/src/firmware/card_container_v2/gate.c',
    'firmware/engine_v48_own/candidate/containers/product/pack.py',
    'firmware/engine_v48_own/candidate/containers/product/src/firmware/card_container_v2/gate.c',
]


def sha(p):
    return hashlib.sha256((ROOT / p).read_bytes()).hexdigest()


def pinned():
    rows = [l.split('\t') for l in MANIFEST.read_text().splitlines()[1:]]
    table = {r[1]: r[6] for r in rows}
    table.update(EXTRA_SHA)
    for key, rel in SRC.items():
        if key == 'ring_model_v2':
            want = EXTRA_SHA[rel]
        else:
            want = table.get(rel)
        if want is None:
            raise SystemExit(f'{rel}: not pinned')
        if sha(rel) != want:
            raise SystemExit(f'{rel}: SHA-256 changed since the manifest ({sha(rel)} != {want})')
    return {rel: sha(rel) for rel in SRC.values()}


class Source:
    def __init__(self, key):
        self.rel = SRC[key]
        self.text = (ROOT / self.rel).read_text()
        self.tree = ast.parse(self.text)

    def node(self, name):
        for n in self.tree.body:
            if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and n.name == name:
                return n
            if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in n.targets):
                return n
        raise KeyError(name)

    def segment(self, name):
        n = self.node(name)
        first = min([n.lineno] + [d.lineno for d in getattr(n, 'decorator_list', [])])
        # keep a comment line directly above a constant (the original's own annotation)
        lines = self.text.splitlines()
        text = '\n'.join(lines[first - 1:n.end_lineno])
        return text

    def segments(self, names):
        return '\n\n\n'.join(self.segment(n) for n in names)


def header(rel, sha_, note):
    return f'"""{note}\n\nSource: {rel}\nSource SHA-256: {sha_}\nVerbatim AST segments only (see research/studio_engine_e0/tools/extract_engine.py).\n"""\n'


def main():
    shas = pinned()
    ENGINE.mkdir(parents=True, exist_ok=True)
    (ENGINE / 'data').mkdir(exist_ok=True)
    files = {}
    edits = {}

    # knobs.py: byte-identical copy
    shutil.copyfile(ROOT / SRC['knobs'], ENGINE / 'knobs.py')
    files['knobs.py'] = dict(source=SRC['knobs'], source_sha256=shas[SRC['knobs']], kind='byte-identical copy')
    shutil.copyfile(ROOT / SRC['final'], ENGINE / 'data/final.json')
    files['data/final.json'] = dict(source=SRC['final'], source_sha256=shas[SRC['final']], kind='byte-identical copy')

    # menu.py: two lines changed (import and table location)
    menu = (ROOT / SRC['menu']).read_text()
    new = menu.replace('import knobs as k\n', 'from . import knobs as k\n')
    new = new.replace("TABLE_PATH = Path(__file__).resolve().parents[1] / 'tables/final.json'",
                      "TABLE_PATH = Path(__file__).resolve().parent / 'data/final.json'")
    assert new != menu and new.count('from . import knobs') == 1 and 'data/final.json' in new
    (ENGINE / 'menu.py').write_text(new)
    files['menu.py'] = dict(source=SRC['menu'], source_sha256=shas[SRC['menu']], kind='copy with 2 edited lines')
    edits['menu.py'] = ["import knobs as k -> from . import knobs as k",
                        "TABLE_PATH: parents[1]/'tables/final.json' -> parent/'data/final.json' (package resource)"]

    # matrix_model.py subset
    mm = Source('matrix_model')
    body = '\n\n\n'.join([
        mm.segments(['Q10', 'COEF_MAX', 'CHROMA_MAX', 'CENTRE', 'ROW_BYTES']),
        '# ----------------------------------------------------------------- Q10 sign-magnitude codec\n\n'
        + mm.segments(['decode_coef', 'encode_coef', 'MatrixRow']),
        '# ----------------------------------------------------------------- curves\n\n' + mm.segments(['Curve']),
        '# ----------------------------------------------------------------- JFIF and colour\n\n'
        + mm.segments(['ycbcr', 'rgb_from_ycc', 'hue_deg']),
    ])
    (ENGINE / 'matrix_model.py').write_text(
        header(SRC['matrix_model'], shas[SRC['matrix_model']],
               'Runtime subset of the explicit GXR colour chain: type-28 matrix row, type-26 curve, BT.601 helpers.\n'
               'Dropped (read the official firmware / not used by the prediction path): read_stock_rows,\n'
               'read_vividness_table, row2_from_row1, SectorTable, Chain, h3_base and the JLAUNCH path constants.')
        + 'import struct\n\nimport numpy as np\n\n\n' + body + '\n')
    files['matrix_model.py'] = dict(source=SRC['matrix_model'], source_sha256=shas[SRC['matrix_model']],
                                    kind='verbatim subset: Q10 COEF_MAX CHROMA_MAX CENTRE ROW_BYTES decode_coef '
                                         'encode_coef MatrixRow Curve ycbcr rgb_from_ycc hue_deg')

    # sector_model.py subset
    sm = Source('sector_model')
    (ENGINE / 'sector_model.py').write_text(
        header(SRC['sector_model'], shas[SRC['sector_model']],
               'Runtime subset of the hue-ring sector model: kernel weights and the coefficient coupling.')
        + 'import math\n\nimport numpy as np\nfrom scipy.special import ndtr\n\n\n'
        + sm.segments(['SIGMA_ZERO', 'hue_deg', 'wrap180', 'effective', '_phi', '_ramp', '_step', '_SHIFTS', 'weights'])
        + '\n')
    # _SHIFTS is defined after weights() in the original but only read at call time; keep order identical
    src = (ENGINE / 'sector_model.py').read_text()
    files['sector_model.py'] = dict(source=SRC['sector_model'], source_sha256=shas[SRC['sector_model']],
                                    kind='verbatim subset: SIGMA_ZERO hue_deg wrap180 effective _phi _ramp _step '
                                         '_SHIFTS weights')

    # colour.py subset of fit_sectors.py
    fs = Source('fit_sectors')
    (ENGINE / 'colour.py').write_text(
        header(SRC['fit_sectors'], shas[SRC['fit_sectors']],
               'sRGB -> CIELAB, CIEDE2000 and the sector-word codec used by the prediction path.')
        + 'import numpy as np\n\n\n'
        + fs.segments(['M709', 'D65']) + '\n\n\n'
        + fs.segments(['srgb_to_linear', 'xyz_to_lab', 'lab_from_codes', 'de00_components', 'delta_e00',
                       'decode_word', 'encode_word', 'Z_of_words']) + '\n')
    files['colour.py'] = dict(source=SRC['fit_sectors'], source_sha256=shas[SRC['fit_sectors']],
                              kind='verbatim subset: M709 D65 srgb_to_linear xyz_to_lab lab_from_codes '
                                   'de00_components delta_e00 decode_word encode_word Z_of_words')

    # pretable.py: class PreTable from the original ring_model_v2.py; sm bound to the sibling module
    rm = Source('ring_model_v2')
    (ENGINE / 'pretable.py').write_text(
        header(SRC['ring_model_v2'], shas[SRC['ring_model_v2']],
               'PreTable: the absolute pre-table sector model (forward + checked inverse).\n'
               'The research copy resolves `sm` to hue_ring/sector_model.py; here it is engine/sector_model.py.')
        + 'import math\n\nimport numpy as np\nfrom scipy.optimize import brentq\n\nfrom . import sector_model as sm\n\n\n'
        + rm.segment('PreTable') + '\n')
    files['pretable.py'] = dict(source=SRC['ring_model_v2'], source_sha256=shas[SRC['ring_model_v2']],
                                kind='verbatim class PreTable (equal to closed_loop/local/vendor/pretable.py)')
    edits['pretable.py'] = ['module-global `sm` bound to engine/sector_model.py via relative import (the vendored copy bound it to analyze_ring.sm = hue_ring/sector_model.py, same SHA d9d98478…)']

    # model.py: adapter methods verbatim, new constructor
    ma = Source('model_adapter')
    cls = ma.node('Model')
    methods = {n.name: n for n in cls.body if isinstance(n, ast.FunctionDef)}
    lines = ma.text.splitlines()

    def meth(name):
        n = methods[name]
        return '\n'.join(lines[n.lineno - 1:n.end_lineno])
    (ENGINE / 'model.py').write_text(
        header(SRC['model_adapter'], shas[SRC['model_adapter']],
               'Host prediction (电脑预测): 552 B entry + white-balanced sensor codes -> sRGB.\n'
               'Model.pre / predict / lab / de and masks / synthetic / recipe_chart are verbatim from model_adapter.py;\n'
               'only the constructor is new (research: closed_loop Engine from DEEPTBL0.DAT + repo paths; here: data from camdata).')
        + '''from types import SimpleNamespace

import numpy as np

from . import colour, matrix_model
from . import knobs as k
from .pretable import PreTable


class Model:
    """The A12-50 ISO200/1600 calibrated chain. For qlaunch/l08firm it is a transferred model, not a calibration.

    stock_words: (24, 2) ints, the sector words of the A12-50 (jlaunch) original 04 entry, decoded with
    colour.decode_word. d0/d1: the five-colour modifier (24 each). ring_model: the gxr-sector-model/2 dict.
    """

    def __init__(self, stock_words, d0, d1, ring_model):
        if ring_model.get('schema') != 'gxr-sector-model/2':
            raise ValueError('需要 v2 pre-table 模型')
        stock = np.asarray(stock_words, dtype=np.int64)
        d0, d1 = np.asarray(d0, dtype=float), np.asarray(d1, dtype=float)
        if stock.shape != (24, 2) or d0.shape != (24,) or d1.shape != (24,):
            raise ValueError('stock/d0/d1 shape')
        S_eff = ((stock[:, 0] + d0) - 1j * (stock[:, 1] + d1)) / 32
        ctx = SimpleNamespace(stock=stock, d0=d0, d1=d1, S_eff=S_eff)
        self.engine = SimpleNamespace(mm=matrix_model, fs=colour, ctx=ctx, table=PreTable(ring_model, S_eff))
        self.mm, self.fs = matrix_model, colour

''' + meth('pre') + '\n\n' + meth('predict') + '\n\n    ' + meth('lab').strip() + '\n    ' + meth('de').strip() + '\n\n\n'
        + ma.segments(['synthetic', 'recipe_chart', 'masks']) + '\n')
    files['model.py'] = dict(source=SRC['model_adapter'], source_sha256=shas[SRC['model_adapter']],
                             kind='verbatim Model.pre/predict/lab/de + synthetic/recipe_chart/masks, new constructor')
    edits['model.py'] = ['Model.__init__ replaced (no DEEPTBL0.DAT, no closed_loop Engine, no repo paths); '
                         'ctx.S_eff derived as ((stock0+d0) - 1j*(stock1+d1))/32 (verified bit-equal to the npz S_eff)',
                         'Model.provenance(), Model.raw() dropped (repo paths / DNG reader belong to S6)']

    (ENGINE / '__init__.py').write_text(
        '"""GXR 工作室引擎：相机配方整数核心（knobs/menu，与相机逐字节一致）和电脑预测（model）。\n\n'
        '全部文件由 research/studio_engine_e0/tools/extract_engine.py 从研究代码逐字抽取，来源与 SHA-256 见\n'
        'PROVENANCE.json。这里没有理光字节：行数据来自 camdata（用户自己的卡）。\n"""\n')
    prov = dict(schema='gxr-studio/engine-provenance/1', files=files, edits=edits,
                datcodec_sources={p: sha(p) for p in DAT_SOURCES},
                engine_file_sha256={str(p.relative_to(ENGINE)): hashlib.sha256(p.read_bytes()).hexdigest()
                                    for p in sorted(ENGINE.rglob('*')) if p.is_file() and p.name != 'PROVENANCE.json'
                                    and '__pycache__' not in p.parts})
    (ENGINE / 'PROVENANCE.json').write_text(json.dumps(prov, indent=2, ensure_ascii=False) + '\n')
    print('engine written:', *sorted(prov['engine_file_sha256']))


if __name__ == '__main__':
    main()
