"""Evaluation-only adapters. Original R1 artifacts and all candidate records are immutable."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C

R1 = C.LOCAL
C.LOCAL = R1 / 'r2'
C.LOCAL.mkdir(exist_ok=True)
C.os.environ.update(TMPDIR=str(C.LOCAL), MPLCONFIGDIR=str(C.LOCAL / 'mpl'))
FILM = C.ROOT / 'research/film_looks_r2/local'
PLANNED = (
    ('Eterna BB', 'full', '05'), ('Leica Classic', 'full', '06'),
    ('Kodachrome25', 'full', '07'), ('Gold 200', 'full', '08'),
    ('Acros official', 'Look', None), ('ARRI Classic709', 'Look', None),
    ('M9 STD', 'Look', None), ('instax mini', 'Look', None),
    ('HNCS HiCon', 'Look', None), ('HNCS LowSat', 'Look', None),
    ('Ektachrome 100', 'Look', None), ('Provia 100F', 'Look', None),
    ('Portra 800', 'Look', None),
)
STYLE_INDICES = {'Eterna BB': 9, 'Leica Classic': 15, 'ARRI Classic709': 6,
                 'M9 STD': 17, 'HNCS HiCon': 18, 'HNCS LowSat': 23, 'Acros official': 53}


def tiny_score(score):
    if score is None:
        return None
    return {k:score[k] for k in ('de00', 'baseline_de00', 'similarity_percent')}


def score(pred, want, base):
    error = C.de(pred, want, 'D65')
    den = C.de(base, want, 'D65')
    e, d = C.stats(error), C.stats(den)
    return dict(de00=e, baseline_de00=d,
                similarity_percent=None if d['median'] < .25 else 100*(1-e['median']/d['median']))


def same_scene_target(style, xyz, base, legacy_want=None):
    """Owner-selected scene-light convention, without fitting or record changes."""
    from targets import Targets
    if not hasattr(same_scene_target, 'renderer'):
        same_scene_target.renderer = Targets()
    t = same_scene_target.renderer
    name = style['name']
    if style['kind'] == 'film':
        return t.current_target(name, None, xyz, base, None)[0]
    if name == 'Acros official':
        return t.current_target('Acros', None, xyz, base, None)[0]
    original = style['target_definition']
    cube = t.cube(original['source'], original['source_sha256'])
    target = C.Target(cube, original['input'], original['output'])
    from gxr_studio.lut.spaces import to_srgb
    encoded = C.xyz_to_encoded(xyz, target.input_space, target.input_gamut)
    output = cube.apply(encoded)
    return C.np.clip(to_srgb(output, target.output_space, target.output_gamut), 0, 1)*255


def frozen_target(style, xyz, base, raw=None):
    from targets import Targets
    if not hasattr(frozen_target, 'renderer'):
        frozen_target.renderer = Targets()
    t = frozen_target.renderer
    if style['kind'] == 'film':
        return t.current_target(style['name'], raw, xyz, base, None)[0]
    if style['name'] == 'Acros official':
        return t.current_target('Acros', raw, xyz, base, None)[0]
    return t.old_target(style['name'], raw, xyz, base)[0]


def decision(phase, what, why, evidence, result):
    C.decision('r2-' + phase, what, why, evidence, result)
