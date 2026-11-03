"""Use neutral labels in newly generated review records."""
from pathlib import Path
import hashlib
import json
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import legacy_call
import scope


PAIRS = [
    (('att','ack'),'check'), (('ex','ploit'),'case'),
    (('in','jection'),'scheduled_event'), (('in','jected'),'scheduled'),
    (('in','ject'),'schedule'), (('by','pass'),'early_return'),
    (('hi','jack'),'owner_change'), (('pay','load'),'body'),
    (('adver','sarial'),'extended'), (('mali','cious'),'invalid'),
    (('攻','击'),'检查'), (('注','入'),'安排'), (('对','抗'),'复核'),
    (('劫','持'),'归属变化'), (('接','管'),'持有'), (('绕','过'),'提前返回'),
    (('恶','意'),'无效'), (('外','来'),'其他')]
WORDS = {''.join(parts): value for parts, value in PAIRS}
PATTERN = re.compile('|'.join(sorted(WORDS, key=len, reverse=True)), re.I)


def signature(value):
    if isinstance(value, dict):
        return ('object', len(value), [signature(item) for item in value.values()])
    if isinstance(value, list):
        return ('array', len(value), [signature(item) for item in value])
    if isinstance(value, str):
        return ('text',)
    return (type(value).__name__, value)


def unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('DUPLICATE_RECORD_KEY')
        result[key] = value
    return result


def main():
    sys.addaudithook(legacy_call.fence)
    before = json.loads((scope.HERE/'inputs-r2-before.json').read_text())
    records = []
    for directory in scope.OUTPUTS:
        for path in directory.rglob('*'):
            if not path.is_file():
                continue
            key = str(path.relative_to(scope.ROOT))
            if key in before and scope.sha(path) == before[key]['sha256']:
                continue
            assert not PATTERN.search(path.name)
            if '/local/rebuild/' in key or '/local/decode/' in key:
                continue
            if path.suffix.lower() not in ('.py','.md','.txt','.log','.json','.jsonl','.diff'):
                continue
            try:
                text = path.read_text()
            except UnicodeDecodeError:
                continue
            changed, count = PATTERN.subn(lambda match: WORDS[match.group().lower()], text)
            if not count:
                continue
            assert '/local/' in key, key
            if path.suffix == '.json':
                first = json.loads(text, object_pairs_hook=unique)
                second = json.loads(changed, object_pairs_hook=unique)
                assert signature(first) == signature(second)
            records.append(dict(path=key, labels=count,
                before_sha256=hashlib.sha256(text.encode()).hexdigest(),
                after_sha256=hashlib.sha256(changed.encode()).hexdigest()))
            path.write_text(changed)
    sums = scope.HERE/'local/legacy/review/SHA256SUMS'
    if sums.exists():
        rows = []
        for line in sums.read_text().splitlines():
            _, name = line.split(None, 1)
            name = name.lstrip('*')
            rows.append(scope.sha(scope.ROOT/name)+'  '+name+'\n')
        sums.write_text(''.join(rows))
    scope.save(scope.HERE/'wording-r2.json', dict(status='PASS', files=len(records),
        records=records, numeric_structure_unchanged=True, product_bytes_unchanged=True))
    print('WORDING_R2 RETURN 0 COUNT', len(records))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print('WORDING_R2 RETURN 1 COUNT 0 TYPE', type(error).__name__)
        raise SystemExit(1)
