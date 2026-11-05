"""Apply the official Acros handoff as a manifest-only, dependency-checked change."""
from pathlib import Path
import copy
import json
import shutil
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C
import records as R

def main():
    C.setup(); C.compute_gate('official-acros-manifests')
    source = C.ROOT/'research/film_looks_r2'
    handoff_path = source/'local/acros_official_handoff.json'
    handoff = json.loads(handoff_path.read_text())
    stage = C.LOCAL/'stages/c040-only-r1'
    if not stage.exists():
        stage.mkdir(parents=True)
        for profile in ('test', 'release'):
            a = C.artifact(profile, 'model')
            shutil.copytree(a['package'], stage/profile/'package')
            shutil.copytree(a['build'], stage/profile/'build')
            shutil.copyfile(a['records'], stage/profile/'records.json')
    proof = []
    for profile in ('test', 'release'):
        a = C.artifact(profile, 'model')
        manifest = json.loads(a['records'].read_text())
        for u, name in enumerate(('a12-50', 'a12-28', 'mount-a12')):
            row = next(r for r in handoff['profiles'] if r['unit'] == name)
            dep = row['base_dependencies'][profile]
            assert row['flags'] == dep['required_flags'] == dep['slot05_flags'] == 1
            assert row['look_base_slot'] == dep['actual_referenced_base_slot'] == 3
            assert row['look_unit_mask'] == 1 << u
            assert row['reference_exact_checked'] and row['quality_passes'] and row['quantization_passes'] == 128
            unit = manifest['units'][u]
            for slot, digest in ((3, dep['base03_sha256']), (5, dep['slot05_sha256'])):
                base = next(r for r in unit['builtins'] if r['slot'] == slot)
                assert base['sha256'] == digest, (profile, name, slot, base['sha256'], digest)
                assert (C.ROOT/base['file']).read_bytes()[1] == 1
            for target, file, digest in (
                ('Acros', row['record_file'], row['record_sha256']),
                ('Tri-X 400', dep['compatible_TriX_file'], dep['compatible_TriX_sha256']),
            ):
                raw = Path(file).read_bytes()
                assert len(raw) == 552 and C.sha(raw) == digest and raw[0] == 3 and raw[1] == 1
                dest = C.LOCAL/'records'/(digest+'.bin'); dest.write_bytes(raw)
                entry = next(r for r in unit['looks'] if r['name'] == target)
                old = entry['sha256']
                entry.update(file=str(dest.relative_to(C.ROOT)), sha256=digest,
                    source='film_looks_r2 official Acros handoff' if target == 'Acros' else 'film_looks_r2 required compatible Tri-X companion',
                    exact_identity=target == 'Acros')
                if target=='Acros':
                    entry['quantization_passes']=128
                    entry['requires']=dict(builtins={'3':dep['base03_sha256'],'5':dep['slot05_sha256']},looks={'Tri-X 400':dep['compatible_TriX_sha256']})
                proof.append(dict(profile=profile, unit=name, name=target, old_sha256=old,
                    record_sha256=digest, base03_sha256=dep['base03_sha256'], slot05_sha256=dep['slot05_sha256']))
        manifest.update(official_acros_handoff_sha256=C.sha(handoff_path.read_bytes()), official_acros_records=3)
        C.save(a['records'], manifest); R.read_manifest(a['records'])
        # This also verifies content identities after global descriptor merging.
        R.serialize(a['records'])
    files = [source/'ACROS.md', handoff_path, source/'local/acros_verification.json']
    files += [Path(r['record_file']) for r in handoff['profiles']]
    frozen=[]
    for file in files:
        raw=file.read_bytes(); rel=file.relative_to(C.ROOT); dest=C.LOCAL/'inputs'/rel
        dest.parent.mkdir(parents=True, exist_ok=True); dest.write_bytes(raw)
        frozen.append(dict(path=str(rel), sha256=C.sha(raw), bytes=len(raw)))
    C.save(C.LOCAL/'official-acros-inputs.json', dict(status='PASS', files=frozen, rows=proof,
        engine_changes=0, slot_changes=0, flags=1))
    print(json.dumps(dict(status='PASS', official_records=6, companion_records=6, engine_changes=0)))

if __name__ == '__main__': main()
