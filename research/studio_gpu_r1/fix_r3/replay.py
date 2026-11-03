"""Re-run r2/r3 cases and retain each required adaptation as a diff."""

import argparse
import difflib
import hashlib
import json
import os
from pathlib import Path

OUT = Path(__file__).resolve().parent
REVIEW = OUT.parent.parent / 'review_studio_gpu_preview_r3'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('case', choices=('extra', 'loop', 'contracts'))
    args = parser.parse_args()
    filename = {'extra': 'extra_boundaries.py', 'loop': 'windows_loop_guard.py', 'contracts': 'windows_contracts.py'}[args.case]
    original = (REVIEW / filename).read_text()
    current = original
    if args.case == 'extra':
        current = current.replace('from gxr_studio.cards.importer import ImportOptions, stage_file',
                                  'from gxr_studio.cards.importer import CardReadError, ImportOptions, stage_file')
        current = current.replace('def open_rb(self, path):', 'def open_rb(self, path, **kwargs):')
        current = current.replace('return super().open_rb(path)', 'return super().open_rb(path, **kwargs)')
        old = """        staged = stage_file(reader, Card(card, 'SYNTHETIC'), cf, lib, ImportOptions(min_free_bytes=0, make_thumbs=False), threading.Event())
        content = staged.path.read_bytes()
        staged.path.unlink()
    result = {'swapped':reader.swapped,'staged_content':content.decode(),'read_other_directory':content == other,'size':len(content),'sha256':hashlib.sha256(content).hexdigest()}
    assert reader.swapped
"""
        new = """        error, content = None, None
        try:
            staged = stage_file(reader, Card(card, 'SYNTHETIC'), cf, lib, ImportOptions(min_free_bytes=0, make_thumbs=False), threading.Event())
            content = staged.path.read_bytes()
            staged.path.unlink()
        except CardReadError as exc:
            error = type(exc).__name__ + ':' + str(exc)
        assert not list(lib.staging_dir.iterdir())
    result = {'swapped':reader.swapped,'staged_content':None if content is None else content.decode(),'read_other_directory':content == other,'error':error}
    assert reader.swapped and content is None and error is not None
"""
        assert old in current
        current = current.replace(old, new)
    elif args.case == 'loop':
        old = "assert error and len(after) == len(before) + 1 and '127.0.0.1' in after[-1]"
        assert old in current
        current = current.replace(old, 'assert error is None and after == before == []')
    target = OUT / filename
    target.write_text(current)
    (OUT / (filename + '.diff')).write_text(''.join(difflib.unified_diff(original.splitlines(True), current.splitlines(True),
                                                                    fromfile='r3-original/' + filename, tofile='fix-r3/' + filename)))
    (OUT / (filename + '-input.json')).write_text(json.dumps(dict(original=str(REVIEW / filename),
                                                                 original_sha256=hashlib.sha256(original.encode()).hexdigest(),
                                                                 replay_sha256=hashlib.sha256(current.encode()).hexdigest()), indent=2) + '\n')
    assert Path(os.environ['REVIEW_OUT']) == OUT
    exec(compile(current, str(target), 'exec'), {'__file__': str(target), '__name__': '__main__'})


if __name__ == '__main__':
    main()
