from pathlib import Path
import hashlib
import json
import struct
import zlib

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'research/review_g135_gpt'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def files(folder):
    return {str(path.relative_to(folder)): path for path in folder.rglob('*') if path.is_file() and not any(part in ('local', '__pycache__') for part in path.relative_to(folder).parts)}


dat = (ROOT / 'firmware/package_v37_g135/local/SD_ROOT/GXRCE.DAT').read_bytes()
body = (ROOT / 'firmware/package_v37_g135/local/SD_ROOT/ilaunch3').read_bytes()
engine_root = ROOT / 'firmware/engine_v53_g135'
prior_root = ROOT / 'firmware/engine_v51_g131'
old, new = files(prior_root), files(engine_root)
changed = [name for name in sorted(old.keys() & new.keys()) if old[name].read_bytes() != new[name].read_bytes()]
added = sorted(new.keys() - old.keys())
removed = sorted(old.keys() - new.keys())
knobs = [name for name in new if '/kv2/' in name]
assert all(name in old and old[name].read_bytes() == new[name].read_bytes() for name in knobs)
header = bytearray(dat[:256])
header[20:24] = bytes(4)
assert struct.unpack_from('>I', dat, 20)[0] == zlib.crc32(header)
assert struct.unpack_from('>I', dat, 24)[0] == zlib.crc32(dat[256:])
assert struct.unpack_from('>I', dat, 28)[0] == 135
assert struct.unpack_from('>I', dat, 16)[0] == len(dat) == 89572
start, length = struct.unpack_from('>II', dat, 132)
engine = (engine_root / 'candidate/local/full-r13/engine.bin').read_bytes()
assert dat[start:start + length] == engine
prior_dat = (prior_root / 'candidate/local/full-r13/GXRCE.DAT').read_bytes()
current_section, current_length = struct.unpack_from('>II', dat, 204)
prior_section, prior_length = struct.unpack_from('>II', prior_dat, 204)
assert current_length == prior_length == 20776
assert dat[current_section:current_section + current_length] == prior_dat[prior_section:prior_section + prior_length]
resident_id = dat[80:112]
assert body.count(resident_id) == 1
block = dat[-17384:]
controls = []
for unit in range(3):
    recipe = block[64 + 16 * (unit * 8 + 2):][:16]
    first = struct.unpack_from('>H', recipe, 4)[0]
    items = [block[448 + 16 * index] for index in range(first, first + recipe[2])]
    assert items == [1, 2, 3, 4, 9]
    controls.append({'unit': ['50mm', '28mm', 'mount'][unit], 'slot': 3, 'controls': items})
rows = json.loads((ROOT / 'research/review_g135/regressions.json').read_text())
classified = [{key: row[key] for key in ['name', 'family', 'unit', 'group', 'outcome', 'returncode', 'basis']} for row in rows if row['outcome'] in ('FAIL_OLD_DESIGN_TEXT', 'FAIL_RETIRED_FUNCTION', 'FAIL_ORIGINAL_READ', 'TOOL_PREREQ')]
assert len(classified) == 24
summary = {'status': 'PASS_STATIC', 'dat_sha256': sha(dat), 'body_sha256': sha(body), 'engine_sha256': sha(engine), 'resident_build_id': resident_id.hex(), 'resident_id_occurrences_in_body': 1, 'generation': 135, 'bytes': len(dat), 'changed_paths': changed, 'added_paths': added, 'removed_paths': removed, 'unchanged_knobs_files': len(knobs), 'seventh_section_equal_g131': True, 'slot03_controls': controls, 'classified_rows': len(classified), 'source_pycache_files': [str(path.relative_to(ROOT)) for path in engine_root.rglob('*.pyc')]}
(OUT / 'evidence/static-review.json').write_text(json.dumps(summary, indent=2) + '\n')
(OUT / 'evidence/classified-24.json').write_text(json.dumps(classified, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(summary))
