"""Verify unchanged inputs and bind this report and its evidence to SHA256SUMS."""
from pathlib import Path
import datetime
import hashlib
import json
import os
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
STUDIO = Path('/Volumes/Workspace/Scratch/worktrees/gxr-studio/g156-codec')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    before = json.loads((HERE/'evidence/inputs-before.json').read_text())
    changed = [name for name,wanted in before['sha256'].items()
               if not Path(name).is_file() or sha(Path(name)) != wanted]
    assert not changed, changed
    env = {**os.environ,'GIT_OPTIONAL_LOCKS':'0'}
    def git(root,*args):
        return subprocess.check_output(['git','-C',str(root),*args],env=env).decode().strip()
    assert git(STUDIO,'rev-parse','HEAD') == before['studio_head']
    assert git(STUDIO,'status','--short','--untracked-files=all') == ''
    dat = json.loads((HERE/'evidence/dat-audit.json').read_text())
    assert len(dat['real_packages']) == 4 and len(dat['other_generations']) == 11
    assert all(row.get('rejected_wrong_bank_all_three') for row in dat['other_generations'])
    assert len(dat['mixed_files']) == 4 and all(row['studio_accepts'] for row in dat['mixed_files'])
    native = json.loads((HERE/'parent-generation/evidence/independent-native-generations.json').read_text())
    assert native['status'] == 'PASS' and len(native['rows']) == 18
    intake = json.loads((HERE/'evidence/intake-audit.json').read_text())
    assert len(intake['rows']) == 16
    assert (HERE/'REVIEW.md').read_text().splitlines()[0] == '修改后再合并'
    integrity = json.loads((HERE/'evidence/integrity.json').read_text())
    integrity.update(checked_files=len(before['sha256']),changed=[],
                     finished_check_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                     studio_head=git(STUDIO,'rev-parse','HEAD'),studio_status='',
                     parent_head=git(ROOT,'rev-parse','HEAD'),parent_status=git(ROOT,'status','--short','--untracked-files=all'))
    (HERE/'evidence/integrity.json').write_text(json.dumps(integrity,ensure_ascii=False,indent=2)+'\n')
    paths = set(HERE.glob('*.py')) | set(HERE.glob('*.mjs')) | {HERE/'REVIEW.md',HERE/'readonly.sb',HERE/'.gitignore'}
    paths.update(p for p in (HERE/'evidence').iterdir() if p.is_file())
    paths.update(p for p in (HERE/'parent-static/evidence').iterdir() if p.is_file())
    paths.update(p for p in (HERE/'parent-generation/evidence').iterdir() if p.is_file())
    paths.update((HERE/'parent-static/tmp/r2-format/parsers.dylib',HERE/'tmp/gate155/format/parsers.dylib'))
    changed_pr = git(STUDIO,'diff','--name-only','HEAD^...HEAD').splitlines()
    paths.update(STUDIO/name for name in changed_pr)
    paths.update((STUDIO/'Makefile',STUDIO/'.github/workflows/ci.yml',STUDIO/'uv.lock',STUDIO/'pyproject.toml'))
    paths.update(ROOT/name for name in (
        'research/g156/r2_static.py','research/g156/r2_generation_harness.py','research/g156/common.py',
        'research/v39_g153/format_checks.py','research/v39_g153/dat_format.py',
        'research/g156/REPORT.md','research/review_g156_r1/REVIEW.md'))
    for name in ('g156','g156_test','g155c','g155c_test'):
        paths.add(ROOT/f'firmware/package_v310_{name}/GXRCE.DAT')
    for engine in ('engine_v68_g156','engine_v67_g155c'):
        product = ROOT/'firmware'/engine/'candidate/containers/product'
        paths.update(product/'src/firmware/card_container_v2'/name for name in ('gate.c','semantic.c','common.c'))
        paths.update(product/name for name in ('fx_pool.c','ui_v2_data.c','memory.c','kv2/kv_data.c','kv2/kv_ui.c','kv2/kv_math.c'))
        paths.add(product/'src/firmware/engine/core/eng_data.c')
        paths.update(ROOT/'firmware'/engine/'candidate/local'/build/'engine.elf' for build in ('boot-off','boot-on'))
    lines = []
    for path in sorted(paths):
        assert path.is_file(), path
        label = str(path.relative_to(HERE)) if path.is_relative_to(HERE) else str(path)
        lines.append(f'{sha(path)}  {label}\n')
    (HERE/'SHA256SUMS').write_text(''.join(lines))
    print(json.dumps(dict(input_files_unchanged=len(before['sha256']),checksum_entries=len(paths),
                          verdict='修改后再合并',studio_head=before['studio_head']),ensure_ascii=False))


if __name__ == '__main__':
    main()
