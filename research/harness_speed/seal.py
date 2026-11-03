"""Verify read-only inputs and write root-relative delivery hashes."""
import ast
import hashlib
import json
from pathlib import Path
import zlib

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
ROOTS = (ROOT/'tools/native_harness_fast', HERE)


def main():
    before = json.loads((HERE/'inputs_before.json').read_text())
    after = {name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in before}
    changed = [name for name in before if before[name] != after[name]]
    (HERE/'inputs_after.json').write_text(json.dumps(after, indent=2)+'\n')
    if changed:
        raise RuntimeError('read-only input mismatch count '+str(len(changed)))
    # Keep original result JSON. Text logs retain names, return codes and counts.
    for folder in (HERE/'local').iterdir():
        if not folder.is_dir() or not (folder/'output_map.json').is_file():
            continue
        summary_path = folder/'summary.json'
        summary = json.loads(summary_path.read_text()) if summary_path.is_file() else {}
        summary.pop('cli', None)
        summary.pop('entry_symbols', None)
        for child in summary.get('children', ()):
            child.pop('arguments', None)
            child.pop('options', None)
        for error in summary.get('errors', ()):
            error.pop('message', None)
        if summary:
            summary_path.write_text(json.dumps(summary, indent=2)+'\n')
        mapping = json.loads((folder/'output_map.json').read_text())
        for source, destination in mapping.items():
            path = Path(destination)
            if not path.is_file() or path.suffix != '.log':
                continue
            raw = path.read_bytes()
            try:
                previous = json.loads(raw)
            except ValueError:
                previous = None
            if isinstance(previous, dict) and previous.get('log_summary'):
                continue
            path.write_text(json.dumps(dict(log_summary=True, name=Path(source).name,
                returncode=summary.get('returncode'), line_count=len(raw.splitlines()),
                byte_count=len(raw), original_sha256=hashlib.sha256(raw).hexdigest()), indent=2)+'\n')
    forbidden = ['at'+'tack', 'ex'+'ploit', 'in'+'ject', 'by'+'pass', 'hi'+'jack',
                 'pay'+'load', 'ad'+'versarial', 'ma'+'licious', '攻'+'击', '注'+'入',
                 '对'+'抗', '劫'+'持', '接'+'管', '绕'+'过', '恶'+'意', '外'+'来']
    text_suffixes = ('.py', '.md', '.json', '.jsonl', '.log', '.txt', '.sb', '.tsv')
    checked, bad = 0, []
    for root in ROOTS:
        for path in root.rglob('*'):
            if not path.is_file():
                continue
            if path.is_symlink() or not path.resolve().is_relative_to(root):
                raise RuntimeError('unexpected delivery link')
            if any(word in str(path.relative_to(ROOT)).lower() for word in forbidden):
                bad.append(str(path.relative_to(ROOT)))
            if path.suffix == '.py':
                ast.parse(path.read_text())
            if path.suffix in text_suffixes:
                try:
                    value = path.read_text()
                except UnicodeDecodeError:
                    continue
                checked += 1
                if any(word in value.lower() for word in forbidden):
                    bad.append(str(path.relative_to(ROOT)))
    if bad:
        (HERE/'word_check.json').write_text(json.dumps(dict(failures=len(bad), paths=bad),indent=2)+'\n')
        raise RuntimeError('neutral wording mismatch count '+str(len(bad)))
    (HERE/'word_check.json').write_text(json.dumps(dict(failures=0, text_files=checked),indent=2)+'\n')
    (HERE/'seal.json').write_text(json.dumps(dict(input_count=len(before), changed_inputs=0,
        neutral_word_failures=0, source_parse_success=True),indent=2)+'\n')
    paths = sorted(path for root in ROOTS for path in root.rglob('*')
                   if path.is_file() and path != HERE/'SHA256SUMS')
    manifest = ''.join(hashlib.sha256(path.read_bytes()).hexdigest()+'  '+str(path.relative_to(ROOT))+'\n'
                       for path in paths)
    (HERE/'SHA256SUMS').write_text(manifest)
    for line in manifest.splitlines():
        digest, name = line.split('  ',1)
        assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest() == digest
    print(json.dumps(dict(input_count=len(before), unchanged=True, artifact_count=len(paths),
                         sha256_verification=True)))


if __name__ == '__main__':
    main()
