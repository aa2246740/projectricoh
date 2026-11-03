"""Source line anchors and digests for a review of the design claims."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from support import ROOT, file_sha, save

ANCHORS = [
    ('S01', 'firmware/engine_v44_keep/candidate/engine_services/services.c', 143, 212,
     'Detached allocation, rejection of nonempty detail records and current publication.'),
    ('S02', 'firmware/resident_v36/resident/resident.h', 40, 51,
     'Permanent 1968-byte native snapshot prefix.'),
    ('S03', 'firmware/resident_v36/resident/hooks.c', 1, 23,
     'H05 ownership requires layer state 2, but does not validate heap or session.'),
    ('S04', 'firmware/resident_v36/resident/hooks.c', 46, 75,
     'H05 returns before ordinary engine checks and DAT invocation.'),
    ('S05', 'firmware/resident_v36/resident/hooks.c', 77, 99,
     'Close, keep=0 and fault behavior.'),
    ('S06', 'firmware/resident_v36/resident/shared.c', 48, 97,
     'Minimal snapshot validation and resident-only detachment without erasing the object.'),
    ('S07', 'firmware/resident_v36/resident/resident.c', 22, 46,
     'Heap/session/code/UI checks and published-session retirement without freeing.'),
    ('S08', 'firmware/resident_v36/resident/loader.c', 89, 161,
     'Image/session allocation, relocation, once-per-boot publication.'),
    ('S09', 'firmware/engine_v44_keep/candidate/containers/product/adapter.c', 263, 300,
     'Engine-side glyph/reference cells and empty detail source.'),
    ('S10', 'firmware/engine_v44_keep/candidate/containers/product/src/firmware/engine/panel/panel_ui.c', 31, 110,
     'Panel conversion/publication and detach.'),
    ('S11', 'firmware/engine_v44_keep/candidate/engine_services/services.c', 358, 384,
     'UI text service printable-ASCII/length/lease checks.'),
    ('S12', 'firmware/engine_v44_keep/candidate/service_build.py', 1, 22,
     'UI services are linked into the DAT, separate from the fixed resident body.'),
    ('S13', 'firmware/engine_v44_keep/candidate/engine_services/native_seed.c', 1, 28,
     'Live view ownership checks before DAT publication.'),
    ('S14', 'firmware/engine_v44_keep/native_harness/harness.py', 81, 139,
     'Graphics stubs and synthetic font references in the basic harness.'),
]


if __name__ == '__main__':
    records = []
    for key, name, first, last, claim in ANCHORS:
        path = ROOT / name
        lines = path.read_text().splitlines()
        assert len(lines) >= last
        records.append(dict(id=key, path=name, sha256=file_sha(path), first_line=first,
                            last_line=last, claim=claim,
                            source='\n'.join(f'{i}: {lines[i-1]}' for i in range(first,last+1))))
    save('source-anchors.json', dict(status='SOURCE_CAPTURED', anchors=records))
    print('captured', len(records), 'source anchors')
