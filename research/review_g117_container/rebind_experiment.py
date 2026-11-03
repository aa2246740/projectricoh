"""Exercise actual build117 --resident-trust using a clearly fake review ID."""
from pathlib import Path
import hashlib
import json
import sys

OUT = Path(__file__).resolve().parent
CAND = OUT / 'isolated/candidate'
ROOT = OUT.parents[1]
sys.path.insert(0, str(CAND))
import common as c
import build117
import service_build

identity = json.loads((ROOT / 'firmware/resident_v35/local/resident/trust.json').read_text())
identity['resident_build_id'] = bytes(x ^ 255 for x in bytes.fromhex(identity['resident_build_id'])).hex()
identity['review_only_fake_identity'] = True
path = OUT / 'REVIEW_ONLY_FAKE_TRUST.json'
path.write_text(json.dumps(identity, indent=2) + '\n')
c.LOCAL = CAND / 'local/rebind-experiment'
service_build.LOCAL = c.LOCAL / 'resident'
sys.argv = [str(CAND / 'build117.py'), '--resident-trust', str(path)]
build117.main()
rebuilt = c.LOCAL / 'full-r13/GXRCE.DAT'
old = (CAND / 'local/full-r13/GXRCE.DAT').read_bytes()
new = rebuilt.read_bytes()
assert len(old) == len(new)
offsets = [i for i, (a, b) in enumerate(zip(old, new)) if a != b]
assert offsets and all(i in range(20, 24) or i in range(80, 112) for i in offsets)
assert old[256:] == new[256:]
assert (c.LOCAL / 'full-r13/engine.bin').read_bytes() == (CAND / 'local/full-r13/engine.bin').read_bytes()
old_trust = (CAND / 'local/full-r13/trust.bin').read_bytes()
new_trust = (c.LOCAL / 'full-r13/trust.bin').read_bytes()
trust_offsets = [i for i, (a, b) in enumerate(zip(old_trust, new_trust)) if a != b]
assert trust_offsets == list(range(40, 72))
assert hashlib.sha256(old).hexdigest() == '4f5eeaffdfc4df77d9482887b827fe8ec73e7857b13ea76348e3e49c874d0b5a'
rebuilt.rename(rebuilt.with_name('REVIEW_ONLY_FAKE_ID_NOT_FOR_INSTALL.DAT'))
(OUT / 'empirical-rebind.json').write_text(json.dumps(dict(status='PASS_ACTUAL_BUILD117_REBIND',
    changed_dat_offsets=offsets, changed_trust_offsets=trust_offsets, engine_identical=True,
    complete_payload_identical=True, original_review_candidate_unchanged=True,
    identity_is_review_fixture=True), indent=2) + '\n')
print('PASS actual build117 --resident-trust: only DAT[20:24], DAT[80:112], trust.bin[40:72] change')
