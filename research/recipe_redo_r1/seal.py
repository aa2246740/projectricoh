"""Hash inputs and outputs, confirm ignore coverage, optionally remove task Scratch."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import runtime_std as rt
import argparse
import shutil
import subprocess


def ignore_receipt():
    paths = sorted(str(p.relative_to(rt.ROOT)) for p in rt.LOCAL.rglob('*') if p.is_file())
    result = subprocess.run(['git', '-C', str(rt.ROOT), 'check-ignore', '-v', '--stdin'],
        input='\n'.join(paths)+'\n', text=True, capture_output=True, check=True)
    ignored = {line.split('\t', 1)[1] for line in result.stdout.splitlines()}
    assert set(paths) <= ignored, 'Derived output is not ignored'
    rt.dump(rt.LOCAL/'final_ignore_receipt.json', dict(command='git check-ignore -v --stdin',
        checked=len(paths), ignored=len(ignored), output=result.stdout, created_utc=rt.utc()))
    # Include the receipt itself. The second check prevents a newly written
    # local artifact from falling outside the checked set.
    receipt = str((rt.LOCAL/'final_ignore_receipt.json').relative_to(rt.ROOT))
    subprocess.run(['git', '-C', str(rt.ROOT), 'check-ignore', '-v', receipt],
        check=True, capture_output=True)
    return len(set(paths)|{receipt})


def input_receipt():
    materials = rt.read(rt.LOCAL/'materials.json')
    new7 = rt.LOCAL/'new7/materials.json'
    if new7.exists():
        materials = materials+rt.read(new7)
    inputs = {}
    for row in materials:
        for path, expected in [(row['path'], row['sha256']), *[(j['path'], j['sha256']) for j in row['jpeg_pairs']]]:
            if path in inputs:
                assert inputs[path] == expected, 'Input manifest has contradictory hashes'
                continue
            assert rt.sha(path) == expected, 'Original photo changed: '+path
            inputs[path] = expected
    for name, expected in rt.read(rt.LOCAL/'input_freeze.json')['inputs'].items():
        assert rt.sha(rt.ROOT/name) == expected, 'Frozen upstream changed: '+name
        inputs[str(rt.ROOT/name)] = expected
    rt.dump(rt.LOCAL/'final_input_hashes.json', inputs)
    return len(inputs)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--final', action='store_true')
    ap.add_argument('--verify-photo-inputs', action='store_true')
    args = ap.parse_args()
    n_inputs = input_receipt() if args.verify_photo_inputs else None
    if args.final:
        assert rt.SCRATCH.is_relative_to(Path('/Volumes/Workspace/Scratch/tmp/projectricoh'))
        scratch_files = [p for p in rt.SCRATCH.rglob('*') if p.is_file()]
        scratch_bytes = sum(p.stat().st_size for p in scratch_files)
        shutil.rmtree(rt.SCRATCH)
        rt.dump('cleanup.json', dict(task_scratch=str(rt.SCRATCH), removed=True, exists=rt.SCRATCH.exists(),
            files_removed=len(scratch_files), bytes_removed=scratch_bytes, created_utc=rt.utc(),
            persistent_local_candidates_retained=True, no_other_paths_removed=True))
        assert not rt.SCRATCH.exists()
        report = rt.HERE/'REPORT.md'
        if report.exists():
            report.write_text(report.read_text().replace('当前仍在运行阶段，Scratch尚未最终清理。',
                '本任务Scratch已删除，本地候选与证据保留；清理回执见cleanup.json。'))
        progress = rt.HERE/'PROGRESS.md'
        if progress.exists():
            complete=rt.read(rt.HERE/'candidate_registry.json')['completed_main_profiles']==105
            note=('105项主矩阵已完成；MOUNT L1局部能力已开放，完整幅度仍待后续探针。' if complete else '本次封存不代表全量拟合完成。')
            content=progress.read_text().replace('最终清理与封存回执待本轮最后一步。',
                '最终清理与封存回执见cleanup.json和seal_receipt.json。')
            final_line='Scratch已清理，参数与候选留在local/；'+note
            if final_line not in content.splitlines():content+='\n'+final_line+'\n'
            progress.write_text(content)
        state_path=rt.LOCAL/'continuation_work_state.json'
        if state_path.exists():
            state=rt.read(state_path)
            state.update(updated_utc=rt.utc(),current_phase='sealed',scratch_removed=True,
                active_session=None,active_batch=None,
                next_steps=['Read-only audit_final.py --hashes --require-clean; do not rerun numerical or report entrypoints in this sealed copy'])
            rt.dump(state_path,state)
        round2_path=rt.LOCAL/'round2_state.json'
        if round2_path.exists():
            state=rt.read(round2_path)
            state.update(updated_utc=rt.utc(),current_phase='sealed',scratch_removed=True,
                active_sessions=[],all_compute_runs_finished=True)
            rt.dump(round2_path,state)
    ignored = ignore_receipt()
    rt.dump('seal_receipt.json', dict(created_utc=rt.utc(), final=args.final,
        full_main_matrix_complete=rt.read(rt.HERE/'candidate_registry.json')['completed_main_profiles']==105,
        full_task_completion_not_inferred_from_artifact_seal=True,
        photo_inputs_rehashed=n_inputs, ignored_local_files=ignored,
        source_and_output_sha256_manifest='SHA256SUMS',
        no_dat_build_no_firmware_modification=True, no_card_or_live_studio_access=True))
    files = sorted(p for p in rt.HERE.rglob('*') if p.is_file() and p != rt.HERE/'SHA256SUMS')
    (rt.HERE/'SHA256SUMS').write_text(''.join(rt.sha(p)+'  '+str(p.relative_to(rt.HERE))+'\n' for p in files))
    print('Sealed', len(files), 'files; final', args.final, '; photo/source inputs', n_inputs, '; local ignored', ignored)


if __name__ == '__main__':
    main()
