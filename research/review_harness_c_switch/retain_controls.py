from pathlib import Path
import hashlib
import json
import shutil

ROOT = Path('/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh')
OUT = ROOT / 'research/review_harness_c_switch'
TMP = Path('/Volumes/Workspace/Scratch/tmp/projectricoh/review-cswitch')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    record = json.loads((OUT / 'switch/version4-build.json').read_text())
    target = OUT / 'switch/retained-api4'
    target.mkdir(exist_ok=False)
    original_source = TMP / 'version4-core.c'
    source = target / original_source.name
    library = target / Path(record['library']).name
    shutil.copyfile(original_source, source)
    shutil.copyfile(record['library'], library)
    assert sha(source) == record['sources'][str(original_source)]
    assert sha(library) == record['sha256']
    retained = dict(record, library=str(library), sources=dict(record['sources']))
    retained['sources'][str(source)] = retained['sources'].pop(str(original_source))
    retained['command'] = [str(source) if value == str(original_source) else
                           str(library) if value == record['library'] else value for value in record['command']]
    retained['retained_from'] = str(OUT / 'switch/version4-build.json')
    (target / 'build.json').write_text(json.dumps(retained, indent=2) + '\n')
    for name in ['missing-library', 'wrong-abi', 'wrong-library-hash', 'wrong-source-hash']:
        shutil.copyfile(TMP / (name + '.json'), OUT / 'switch' / (name + '-build.json'))
    result = {'api4_library_sha256': sha(library), 'api4_source_sha256': sha(source),
              'retained_library': str(library), 'retained_source': str(source),
              'original_manifest': str(OUT / 'switch/version4-build.json'),
              'relocated_manifest': str(target / 'build.json')}
    (OUT / 'evidence/retained-controls.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
