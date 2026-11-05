"""Module-native C040 geometry; firmware-derived values stay in ignored inputs.

Set GXR_C040_GEOMETRY=legacy50, or pass geometry='legacy50', to replay the
shared-50mm model. Native geometry preserves the measured 50mm residual.
"""
import copy
from functools import lru_cache
import hashlib
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
UNITS = {'a12-50': ('50mm', 'jlaunch3'),
         'a12-28': ('28mm', 'qlaunch3'),
         'mount-a12': ('mount', 'l08firm3')}
ALIASES = {'50mm': 'a12-50', '28mm': 'a12-28', 'mount': 'mount-a12'}


def geometry_mode(geometry=None):
    mode = geometry if geometry is not None else os.environ.get('GXR_C040_GEOMETRY', 'native')
    if mode not in ('native', 'legacy50'):
        raise ValueError('C040 geometry must be native or legacy50')
    return mode


@lru_cache(maxsize=3)
def native_source(unit):
    unit = ALIASES.get(unit, unit)
    key, filename = UNITS[unit]
    official_path = ROOT/'research/module_adapt/local/official_parameters.json'
    official = json.loads(official_path.read_text())['units'][key]
    path = ROOT/'artifacts/firmware/gxr-1.51'/filename
    firmware = path.read_bytes()
    colour = official['rows']['colour1']
    colour_offset = colour['file_offset']
    colour_bytes = bytes.fromhex(colour['hex'])
    if firmware[colour_offset:colour_offset+len(colour_bytes)] != colour_bytes:
        raise ValueError('C080 locator differs from the official parameter receipt')
    offset = colour_offset-26*48
    row = firmware[offset:offset+48]
    codes = tuple(row[::2])
    steps = [b-a for a, b in zip(codes, (*codes[1:], codes[0]+256))]
    if len(row) != 48 or row[1::2] != bytes([64])*24 or not all(2 <= n < 80 for n in steps):
        raise ValueError('Invalid normal C040 row at the independently located bank')
    return dict(unit=unit, codes=codes, file_offset=offset,
                firmware_sha256=hashlib.sha256(firmware).hexdigest(),
                row_sha256=hashlib.sha256(row).hexdigest(),
                parameter_receipt_sha256=hashlib.sha256(official_path.read_bytes()).hexdigest())


def module_spec(spec, unit, geometry=None):
    """Shift native nodes once, retaining all empirical gain/kernel parameters."""
    unit = ALIASES.get(unit, unit)
    if unit not in UNITS:
        raise ValueError('Unknown camera unit: '+str(unit))
    mode = geometry_mode(geometry)
    result = copy.deepcopy(spec)
    previous = result.get('module_c040_geometry')
    if previous:
        if mode == 'native' and previous['unit'] == unit:
            return result
        raise ValueError('C040 geometry already applied; start with the measured 50mm specification')
    if mode == 'legacy50' or unit == 'a12-50':
        return result
    source, origin = native_source(unit), native_source('a12-50')
    change = [(a-b)*360/256 for a, b in zip(source['codes'], origin['codes'])]
    for key in ('nodes_deg', 'nodes_unwrapped_deg', 'sector_centres_deg'):
        result[key] = [a+b for a, b in zip(result[key], change)]
    if not all(b > a for a, b in zip(result['nodes_unwrapped_deg'], result['nodes_unwrapped_deg'][1:])):
        raise ValueError('Native C040 nodes are not monotonic')
    result['module_c040_geometry'] = dict(unit=unit, mode=mode,
        source_sha256=source['firmware_sha256'], row_sha256=source['row_sha256'],
        calibration='measured 50mm residual from native nodes retained')
    return result


def input_map_path(unit, geometry=None):
    """Require the rebuilt input map rather than silently using the old 04 inverse."""
    unit = ALIASES.get(unit, unit)
    if geometry_mode(geometry) == 'legacy50' or unit == 'a12-50':
        return None
    path = ROOT/'research/model_c040_r1/local/calibration'/('input-map-'+unit+'.json')
    if not path.is_file():
        raise FileNotFoundError('Native C040 requires a rebuilt input map: '+str(path))
    return path
