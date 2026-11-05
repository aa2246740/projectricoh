"""Whole-repository generation scan, adapted from the sealed g159 scanner."""
from pathlib import Path
import argparse
import json
import re
import subprocess
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--generation', type=int, default=160)
    parser.add_argument('--tag', default='initial')
    args = parser.parse_args()
    assert args.generation == 160 and re.fullmatch(r'[a-zA-Z0-9_-]+', args.tag)
    C.setup(); C.gate('generation160-whole-repository')
    out = C.LOCAL / 'generation-scans' / args.tag
    assert not out.exists(), 'Keep previous scan evidence; use a new tag'
    out.mkdir(parents=True)
    exclude = ['-g', '!.git', '-g', '!**/.git/**', '-g', '!**/.venv/**',
               '-g', '!**/node_modules/**', '-g', '!**/__pycache__/**', '-g', '!research/g160/**']
    command = ['rg','--files','--hidden','--no-ignore','-g','*.DAT','-g','*.dat','-g','*.bin',*exclude,'.']
    paths = subprocess.check_output(command,cwd=C.ROOT,text=True,stdin=subprocess.DEVNULL).splitlines()
    headers = []
    for i, name in enumerate(paths):
        path = C.ROOT / name
        with path.open('rb') as source: header = source.read(256)
        if len(header) == 256 and header[:8] == b'GXRCE001':
            headers.append(dict(path=str(Path(name)),generation=int.from_bytes(header[28:32],'big'),bytes=path.stat().st_size))
        if (i+1)%25000 == 0: print('BINARY_HEADERS',i+1,'DAT',len(headers),flush=True)
    for profile in ('test','release'):
        relative = str(C.baseline_dat(profile).relative_to(C.ROOT))
        assert any(r['path']==relative and r['generation']==158 for r in headers), 'Delivered baseline positive control'
    assert any('lutprobe' in r['path'] for r in headers), 'Probe coverage positive control'
    # Include known159 assignments as a positive control for source coverage.
    pattern = (r'(?:build_number|generation|GENERATION|ENG_GEN|build)[^\n,;]{0,32}\b(?:160|0[xX][aA]0|159)\b'
               r'|\bg160\b|\bv71_g160\b')
    command = ['rg','-n','--hidden','--no-ignore','-g','*.json','-g','MANIFEST','-g','*.py','-g','*.c','-g','*.h',
               '-g','*.md','-g','*.txt','-g','*.toml','-g','*.yml',*exclude,pattern,'.']
    process = subprocess.run(command,cwd=C.ROOT,text=True,capture_output=True,stdin=subprocess.DEVNULL)
    assert process.returncode in (0,1), process.stderr
    (out/'source-matches.txt').write_text(process.stdout)
    matches=[]; manifests=[]
    for line in process.stdout.splitlines():
        name, number, content = line.split(':',2)
        row=dict(path=str(Path(name)),line=int(number),text=content[:2000]);matches.append(row)
        if (Path(name).suffix=='.json' or Path(name).name=='MANIFEST') and re.search(r'"(?:generation|build_number)"\s*:\s*160\b',content):
            manifests.append(row)
    assert any(r['path']=='research/exif_recipe_tag_r1/local/format_probe.py' and 't.generation = 159' in r['text'] for r in matches), 'Known source positive control'
    packages=[r for r in headers if r['generation']==160]
    result=dict(status='PASS_DAT_AND_MANIFEST_SCAN' if not packages and not manifests else 'FAIL_GENERATION_IN_USE',
                generation=160,binary_paths_examined=len(paths),DAT_headers=headers,
                generation_packages=packages,generation_manifests=manifests,source_mentions=matches,
                source_mentions_require_classification=True,source_command=command,
                no_text_size_cutoff=True,actual_DAT_magic='GXRCE001',DAT_created=False)
    C.save(out/'result.json',result)
    print(json.dumps(dict(status=result['status'],binary_paths=len(paths),DAT_headers=len(headers),source_matches=len(matches),generation160_DATs=len(packages))),flush=True)


if __name__=='__main__':main()
