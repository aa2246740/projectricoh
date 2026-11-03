#!/usr/bin/env python3
"""Verify checksums, ignore rules, input preservation, and final packed DNGs offline."""
import sys
from pathlib import Path
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import argparse
import ast
import io
import json
import subprocess
import numpy as np
from PIL import Image
from common import HERE, ROOT, LOCAL, DELIVERY, read, dump, require, sha, mount_check, git_status_outside
from tiff_io import Tiff, sof_info
from predict import decode_card

PUBLIC_SUMS = HERE / 'SHA256SUMS'
LOCAL_SUMS = LOCAL / 'SHA256SUMS'
DELIVERY_SUMS = DELIVERY / 'SHA256SUMS'
EXCLUSIONS = {PUBLIC_SUMS, LOCAL_SUMS, DELIVERY_SUMS, LOCAL / 'verification.json'}


def public_files():
    return sorted([p for p in HERE.rglob('*') if p.is_file() and not p.is_relative_to(LOCAL) and p not in EXCLUSIONS]
                  + [DELIVERY / '.gitignore'])


def private_files():
    return sorted(p for base in (LOCAL, DELIVERY) for p in base.rglob('*')
                  if p.is_file() and p not in EXCLUSIONS and p != DELIVERY / '.gitignore')


def sums(path, files):
    path.write_text(''.join(f'{sha(p)}  {p.relative_to(ROOT)}\n' for p in files))


def check_sums(path, expected):
    require(path.exists(), f'缺少校验和: {path}')
    records = {}
    for line in path.read_text().splitlines():
        digest, name = line.split('  ', 1)
        p = (ROOT / name).resolve()
        require(p.is_relative_to(ROOT) and p not in records and len(digest) == 64, '校验和清单格式不符')
        require(p.exists() and sha(p) == digest, f'校验和不符: {name}')
        records[p] = digest
    require(set(records) == set(expected), f'清单覆盖不完整: {path}')
    return len(records)


def preservation(strict_workspace=False):
    saved = read(LOCAL / 'baseline.json')
    current = git_status_outside()
    changed = [path for path, digest in saved['tracked_files'].items()
               if not (ROOT / path).is_file() or sha(ROOT / path) != digest]
    workspace = dict(git_status_unchanged=current == saved['git_status_outside'],
                     status_added=sorted(set(current) - set(saved['git_status_outside'])),
                     status_removed=sorted(set(saved['git_status_outside']) - set(current)),
                     changed_tracked_files=changed,
                     note='起始快照未更新；范围外变动只报告，不回滚、不计入本任务产物。')
    if strict_workspace:
        require(workspace['git_status_unchanged'] and not changed, '范围外工作区与起始快照不同，见非 strict 验证报告')
    inputs = read(LOCAL / 'inputs.json')
    for path, digest in inputs['sha256'].items():
        require(sha(ROOT / path) == digest, f'只读输入改变: {path}')
    return len(saved['tracked_files']) - len(changed), len(inputs['sha256']), workspace


def ignore_rules():
    require((HERE / '.gitignore').read_text() == 'local/\n', 'research 忽略规则改变')
    require((DELIVERY / '.gitignore').read_text() == '*\n!.gitignore\n', '交付忽略规则改变')
    paths = private_files() + [LOCAL_SUMS, DELIVERY_SUMS, LOCAL / 'verification.json']
    p = subprocess.run(['git', 'check-ignore', '-z', '--stdin'], input=''.join(str(p) + '\0' for p in paths),
                       cwd=ROOT, capture_output=True, text=True, check=True)
    require(set(p.stdout.split('\0')) - {''} == {str(p) for p in paths}, '派生文件没有全部被忽略')
    tracked = subprocess.run(['git', 'ls-files', '-z'], cwd=ROOT, check=True, capture_output=True).stdout.decode().split('\0')
    require(not any(p.startswith(('research/gr_incamera_dev/local/', 'artifacts/gr-incamera-dev/'))
                    and p != 'artifacts/gr-incamera-dev/.gitignore' for p in tracked), '索引含有私有派生数据')
    return len(paths)


def public_content():
    for p in public_files():
        require(p.suffix in ('.py', '.c', '.md') or p.name == '.gitignore', '公开区出现意外文件类型')
        if p.suffix == '.py':
            tree = ast.parse(p.read_text(), filename=str(p))
            for n in ast.walk(tree):
                require(not isinstance(n, ast.Constant) or not isinstance(n.value, bytes) or len(n.value) < 48,
                        '公开代码出现至少 48 字节的内嵌原始数据')
        require(not p.is_symlink(), '公开交付含符号链接')


def verify_dng(manifest):
    card = read(manifest)
    before = Tiff(Path(card['template_path']).read_bytes())
    after = Tiff(Path(card['dng_path']).read_bytes())
    require(sha(card['template_path']) == card['template_sha256'] and sha(card['dng_path']) == card['dng_sha256'], 'DNG 哈希不符')
    require(before.signature() == after.signature() and before.geometry() == after.geometry(), '成品 IFD 或几何改变')
    require(len(before.data) == len(after.data), '成品文件长度改变')
    stop = 0
    for c in sorted(card['mutations'], key=lambda c: (c['start'], c['end'])):
        require(before.data[stop:c['start']] == after.data[stop:c['start']], '未声明的字节改变')
        stop = max(stop, c['end'])
    require(before.data[stop:] == after.data[stop:], '未声明的尾部改变')
    raw = decode_card(card)
    import imagecodecs
    for seg in after.segments(after.raw):
        x, y, w, h = seg['box']
        blob = after.data[seg['offset']:seg['offset'] + seg['capacity']]
        sof_info(blob)
        independent = imagecodecs.ljpeg_decode(blob).reshape(h, w)
        require(np.array_equal(independent, raw[y:y + h, x:x + w]), '成品独立解码不一致')
    for c in card['mutations']:
        if c['reason'].startswith(('RAW:', 'preview:')):
            n = c['payload_bytes']
            require(not any(after.data[c['start'] + n:c['end']]), '旧图像残留在分配区尾部')
    for node in after.ifds:
        if node is after.raw or 256 not in node.entries or after.scalar(node, 259) != 7:
            continue
        for seg in after.segments(node):
            with Image.open(io.BytesIO(after.data[seg['offset']:seg['offset'] + seg['capacity']])) as im:
                im.load()
                require(im.size == (after.scalar(node, 256), after.scalar(node, 257)), '主预览尺寸不符')
    maker = after.maker()
    at = maker.offset - 8 + maker.entries[4].value[0]
    n = maker.entries[3].value[0]
    with Image.open(io.BytesIO(after.data[at:at + n])) as im:
        im.load()
        require(list(im.size) == maker.entries[2].value, 'MakerNote 预览尺寸不符')
    return dict(name=Path(card['dng_path']).name, sha256=card['dng_sha256'], samples=int(raw.size),
                ifd_offsets_preserved=True, pixels_exact=True, previews_decodable=True)


def verify(seal=False, record=False, strict_workspace=False):
    mount_check()
    baseline_n, input_n, workspace = preservation(strict_workspace)
    public_content()
    ignored = ignore_rules()
    cards = [verify_dng(p) for p in sorted((LOCAL / 'cards').glob('*.json'))]
    require({'GR3_colour.DNG', 'GR3_tone.DNG', 'GR4_colour_PRIVATE.DNG'} <= {c['name'] for c in cards},
            '缺少默认的两份 GR III 和一份仅本地 GR IV 测试产物')
    for p in DELIVERY.glob('*.DNG'):
        require(p.name in ('GR3_colour.DNG', 'GR3_tone.DNG'), '外发目录出现未授权 DNG')
    require(read(LOCAL / 'codec-tests.json')['passed'], '编码器测试没有通过')
    require(read(LOCAL / 'dry_run/summary.json')['passed'], '端到端干跑没有通过')
    if seal:
        sums(PUBLIC_SUMS, public_files())
        sums(LOCAL_SUMS, private_files())
        sums(DELIVERY_SUMS, sorted(p for p in DELIVERY.rglob('*') if p.is_file() and p != DELIVERY_SUMS))
    counts = dict(public=check_sums(PUBLIC_SUMS, public_files()),
                  local=check_sums(LOCAL_SUMS, private_files()),
                  delivery=check_sums(DELIVERY_SUMS, sorted(p for p in DELIVERY.rglob('*') if p.is_file() and p != DELIVERY_SUMS)))
    baseline_n, input_n, workspace = preservation(strict_workspace)
    result = dict(passed=True, checksum_base=str(ROOT), checksum_counts=counts, ignored_files=ignored,
                  unchanged_tracked_files=baseline_n, unchanged_readonly_inputs=input_n, cards=cards,
                  outside_scope_git_status_unchanged=workspace['git_status_unchanged'],
                  workspace_changes=workspace, private_data_in_git_index=False,
                  camera_acceptance=False, no_network_operations=True,
                  versions=dict(python=sys.version.split()[0], numpy=np.__version__,
                                pillow=__import__('PIL').__version__, imagecodecs=imagecodecs_version()))
    if record:
        dump(LOCAL / 'verification.json', result)
    print(json.dumps(result, ensure_ascii=False))
    return result


def imagecodecs_version():
    import imagecodecs
    return imagecodecs.__version__


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--seal', action='store_true', help='验证输入后生成完整校验和清单')
    p.add_argument('--record', action='store_true', help='保存不纳入校验和的本次验证日志')
    p.add_argument('--strict-workspace', action='store_true', help='把其他工作导致的范围外变动也作为失败')
    a = p.parse_args()
    verify(a.seal, a.record, a.strict_workspace)
