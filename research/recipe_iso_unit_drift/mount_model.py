"""MOUNT UnitModel loaded with the actual g137 GXRCE.DAT recipe rows (all three units decodable)."""
import sys; from pathlib import Path; sys.path.insert(0, str(Path(__file__).resolve().parent))
from drift_common import *
sys.modules['common'] = load('common', 'research/closed_loop/common.py')
sys.path.insert(0, str(ROOT / 'research/module_adapt'))
import support as s
s.HERE, s.LOCAL = HERE, LOCAL
from unit_model import UnitModel
import calibrate

G137 = 'firmware/package_v38_g137/local/SD_ROOT/GXRCE.DAT'
audit = load('tma_audit', 'research/three_module_audit_r1/audit.py')
SRC = load('drift_deep_sources', 'firmware/stage2l_switch/tools/deep_sources.py')
S3 = ROOT / 'research/gr4_nega_returns_r1/local/mount/candidate/DEEPTBL_mount_gr4_posi_nega_r1.DAT'
S2 = ROOT / 'research/gr4_nega_returns_r1/local/candidate/DEEPTBL_50mm_gr4_posi_nega_r1.DAT'
PIN = {'mount': 0x4686301b}


def g137_modules(path=G137):
    raw, sections, modules = audit.decode(path)
    return {m['name']: m for m in modules}


def entries448(module):
    """Same row split as deep_sources.parse (448 B prefix of entry552); recipe-struct CRC differs in g13x so it is not checked."""
    import struct
    out = {}
    for slot in SRC.TABLE_SLOTS:
        p = module['entries'][slot][:448]
        key, mask = p[0], p[1]
        assert key == slot
        rows = tuple(p[o:o + n] for o, n in zip(SRC.ROW_OFFSETS, SRC.ROW_BYTES))
        control = struct.unpack_from('>H', p, SRC.CONTROL_OFFSET)[0]
        out[f'{slot:02d}'] = dict(slot=slot, mask=mask, rows=rows, control=control)
    stock = out['04']['rows']
    for e in out.values():
        e['written'] = tuple(e['rows'][r] if not bit or e['mask'] & bit else stock[r] for r, bit in enumerate(SRC.ROW_BITS))
    return out


def mount_model():
    mods = g137_modules()
    name = next(n for n in mods if 'mount' in n.lower() or n.lower().startswith('l08'))
    m = UnitModel('mount', iso=200)
    m.base.entries = entries448(mods[name])
    return m, mods, name


if __name__ == '__main__':
    mods = g137_modules()
    print({n: sorted(m['entries']) for n, m in mods.items()})
    m, mods, name = mount_model()
    print('mount module', name, sorted(m.base.entries))
