#!/usr/bin/env python3
"""Check source preservation, ignored data, public syntax and delivery hashes."""
import sys
sys.dont_write_bytecode = True
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import argparse
import ast
import json
import re
import subprocess
import numpy as np
import scipy
import PIL
from common import ROOT, HERE, LOCAL, read, dump, sha, mount_guard, require


def public_files():
    return sorted(p for p in HERE.rglob('*') if p.is_file() and not p.is_relative_to(LOCAL)
                  and p.name != 'SHA256SUMS' and '__pycache__' not in p.parts)


def check_public_payload(path):
    content = path.read_text()
    require(re.search(r'(?i)(?<![0-9a-f])[0-9a-f]{96,}(?![0-9a-f])', content) is None,
            f'公开文件包含至少 48 字节的十六进制串：{path}')
    require(re.search(r'(?:\\x[0-9a-fA-F]{2}){48,}', content) is None,
            f'公开文件包含至少 48 字节的转义串：{path}')
    if path.suffix == '.py':
        tree = ast.parse(content, filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, bytes):
                require(len(node.value) < 48, f'公开文件包含至少 48 字节的 bytes：{path}')
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                compact = ''.join(node.value.split())
                require(not (len(compact) >= 96 and re.fullmatch(r'[0-9a-fA-F]+', compact)),
                        f'公开文件包含分段十六进制串：{path}')


def verify_round_one():
    if not (HERE / 'REPORT_R1.md').exists():
        return {}
    inputs = read(LOCAL / 'tmp/r1_before.json')['sha256']
    require(all(sha(path) == h for path, h in inputs.items()), 'R1 只读输入或 prelim 发生变化')
    names = ['m20261021_r1.json', 'm20261021_r1_gr.json', 'm20261021_r1_analysis.json',
             'gr_targets_20261021_r1.json', 'gr_targets_20261021_r1_iso1600.json',
             'm20261021_r1_screen_refit.json', 'm20261021_r1_screen_refit_gr.json']
    for name in names:
        result = read(LOCAL / name)
        for path, q in result['provenance'].items():
            require(sha(path) == q['sha256'] and q['unchanged'], f'R1 来源变化：{path}')
        if name.startswith('m20261021_r1') and 'frames' in result:
            full = 'screen_refit' not in name
            require(len(result['frames']) == (14 if full else 7), 'R1 帧数不完整')
            require(result['eligible_for_refit'] is (not full), 'R1 回拟资格错误')
            require(result['eligible_refit_sets'] == ['screen'], '只能导出 ISO 200 屏幕组')
            for frame in result['frames']:
                require(frame['eligible_for_refit'] == (frame['set'] == 'screen'), '帧回拟资格错误')
                if frame['meta']['iso'] == 800:
                    require(not frame['measurement_valid'] and frame['iso_status'] == 'ISO 800 未标定',
                            'ISO 800 未标定状态丢失')
    analysis = read(LOCAL / 'm20261021_r1_analysis.json')
    require(all(q['target_shift_de00_max'] == 0. for q in
                analysis['iso800_sensitivity']['fuji_target_invariance'].values()), '05/06 目标依赖 ISP')
    unchanged_signatures = 0
    for before in (LOCAL / 'tmp/before').rglob('*.py'):
        current = HERE / before.relative_to(LOCAL / 'tmp/before')
        old_tree, new_tree = ast.parse(before.read_text()), ast.parse(current.read_text())
        def signatures(tree):
            result = {}
            def visit(node, prefix=''):
                for child in ast.iter_child_nodes(node):
                    if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        result[prefix+child.name] = ast.dump(child.args, include_attributes=False)
                    elif isinstance(child, ast.ClassDef):
                        visit(child, prefix+child.name+'.')
            visit(tree)
            return result
        old, new = signatures(old_tree), signatures(new_tree)
        require(all(new.get(k) == v for k, v in old.items()), f'既有函数签名变化：{current}')
        unchanged_signatures += len(old)
    return {'protected_input_hashes': len(inputs), 'protected_inputs_changed': 0,
            'existing_signatures_unchanged': unchanged_signatures,
            'complete_camera_frames': 14, 'eligible_refit_sets': ['screen'],
            'public_large_byte_strings': 0}


def write_sums(root, files):
    (root / 'SHA256SUMS').write_text(''.join(f'{sha(p)}  {p.relative_to(root).as_posix()}\n' for p in files))


def verify_sums(root):
    sums = root / 'SHA256SUMS'
    require(sums.is_file(), f'{sums} 缺失')
    count = 0
    for line in sums.read_text().splitlines():
        digest, name = line.split('  ', 1)
        p = root / name
        require(p.resolve().is_relative_to(root.resolve()), '校验和路径越界')
        require(p.is_file() and sha(p) == digest, f'校验和不符：{p}')
        count += 1
    return count


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--write-sums', action='store_true')
    args = ap.parse_args()
    volume = mount_guard()
    public = public_files()
    for p in public:
        require(p.suffix not in ('.DAT', '.DNG', '.JPG', '.npz', '.png', '.svg'), '派生文件出现在公开目录')
        check_public_payload(p)
    sample = LOCAL / 'tests/synthetic_capture/synthetic05.DNG'
    subprocess.run(['git', 'check-ignore', '-q', str(sample)], cwd=ROOT, check=True)
    tracked = subprocess.check_output(['git', 'ls-files', '--', str(LOCAL)], cwd=ROOT, text=True)
    require(not tracked.strip(), 'local/ 有已经进入 Git 索引的文件')
    manifest = read(LOCAL / 'vendor_manifest.json')
    require(all(sha(p) == h for p, h in manifest['sources_sha256'].items()), '只读辅助源文件发生变化')
    source_files = set(manifest['sources_sha256'])
    for name in ('dry_ring_measurement.json', 'dry_2e_measurement.json'):
        result = read(LOCAL / name)
        require(not result['eligible_for_refit'], '历史诊断被误标为合格组')
        for path, q in result['provenance'].items():
            require(sha(path) == q['sha256'] and q['unchanged'], '测量来源发生变化')
            source_files.add(path)
    for p in (LOCAL / 'tests').rglob('*candidate.json'):
        c = read(p)
        require(c['firmware_ready'] is False and c['accepted'] is False and c['deployable'] is False,
                '测试候选的待审核标记错误')
    round_one = verify_round_one()
    if args.write_sums:
        dump(LOCAL / 'delivery_verification.json', {'public_files': len(public), 'volume': volume,
            'source_files_checked': len(source_files), 'source_files_changed': 0,
            'local_git_ignored': True, 'local_tracked_files': 0, 'round_one': round_one,
            'versions': {'python': sys.version.split()[0], 'numpy': np.__version__,
                         'scipy': scipy.__version__, 'Pillow': PIL.__version__}})
        write_sums(HERE, public)
        local_files = sorted(p for p in LOCAL.rglob('*') if p.is_file() and p != LOCAL / 'SHA256SUMS')
        write_sums(LOCAL, local_files)
    a, b = verify_sums(HERE), verify_sums(LOCAL)
    print(json.dumps({'public_hashes_verified': a, 'local_hashes_verified': b,
                      'source_files_checked': len(source_files), 'source_files_changed': 0,
                      'local_git_ignored': True, 'round_one': round_one}, ensure_ascii=False))


if __name__ == '__main__':
    main()
