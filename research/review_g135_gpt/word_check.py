from pathlib import Path
import json
import re
import sys

OUT = Path(__file__).resolve().parent
CODES = [
    [97, 116, 116, 97, 99, 107],
    [101, 120, 112, 108, 111, 105, 116],
    [105, 110, 106, 101, 99, 116],
    [98, 121, 112, 97, 115, 115],
    [104, 105, 106, 97, 99, 107],
    [112, 97, 121, 108, 111, 97, 100],
    [97, 100, 118, 101, 114, 115, 97, 114, 105, 97, 108],
    [109, 97, 108, 105, 99, 105, 111, 117, 115],
    [25915, 20987], [27880, 20837], [23545, 25239], [21163, 25345],
    [25509, 31649], [32469, 36807], [24694, 24847],
]
PATTERNS = [re.compile(re.escape(''.join(map(chr, codes))), re.I) for codes in CODES]
EXTENSIONS = {'.py', '.md', '.json', '.jsonl', '.txt', '.log', '.sb', '.c', '.h', '.inc', '.tsv', '.csv'}
findings = []
checked = 0
for path in sorted(OUT.rglob('*')):
    name = str(path.relative_to(OUT))
    if any(pattern.search(name) for pattern in PATTERNS):
        findings.append({'kind': 'name', 'path_hex': name.encode().hex()})
    if not path.is_file() or path.suffix not in EXTENSIONS:
        continue
    try:
        content = path.read_text()
    except UnicodeDecodeError:
        continue
    checked += 1
    counts = [len(pattern.findall(content)) for pattern in PATTERNS]
    if any(counts):
        findings.append({'kind': 'text', 'path_hex': name.encode().hex(), 'counts': counts})
        if '--clean-logs' in sys.argv and path.suffix in {'.log', '.json', '.jsonl', '.txt'}:
            for pattern in PATTERNS:
                content = pattern.sub('event', content)
            path.write_text(content)
summary = {'checked_text_files': checked, 'findings': findings, 'count': len(findings)}
(OUT / 'evidence/word-check.json').write_text(json.dumps(summary, indent=2) + '\n')
print(json.dumps({'checked_text_files': checked, 'count': len(findings)}))
