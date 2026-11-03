"""Private owner registry and per-invocation build destinations."""
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PRIVATE = HERE / 'local/private'
REGISTRY = PRIVATE / 'owners.json'
_roots = {}


def slug(value):
    if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', value):
        raise ValueError('owner must be a lowercase slug, e.g. new-gr4-owner')
    return value


def load():
    record = json.loads(REGISTRY.read_text())
    if record.get('schema') != 'gr-dense-owners/1':
        raise ValueError('unknown owner registry schema')
    return record['owners']


def get(owner):
    slug(owner)
    records = load()
    if owner not in records:
        raise ValueError(f'unknown owner: {owner}; run onboard.py with their original DNG first')
    return records[owner]


def templates():
    return {owner: (entry['template']['path'], entry['template']['sha256'])
            for owner, entry in load().items()}


def private_path(path):
    path = Path(path)
    if path.is_symlink() or not path.resolve().is_relative_to(PRIVATE.resolve()):
        raise ValueError(f'private output must remain under {PRIVATE}: {path}')
    return path.resolve()


def root(owner):
    slug(owner)
    return _roots.get(owner, private_path(PRIVATE / owner))


def set_root(owner, path):
    slug(owner)
    path = private_path(path)
    if not path.is_relative_to((PRIVATE / owner).resolve()):
        raise ValueError('build output must remain in this owner folder')
    _roots[owner] = path
    return path


def register(owner, entry):
    slug(owner)
    records = load()
    if owner in records:
        raise ValueError(f'owner already registered: {owner}; refusing to replace their template')
    records[owner] = entry
    pending = private_path(REGISTRY.with_suffix('.pending.json'))
    with pending.open('x', encoding='utf-8') as handle:
        handle.write(json.dumps(dict(schema='gr-dense-owners/1', owners=records),
                                indent=2, ensure_ascii=False, allow_nan=False) + '\n')
    pending.replace(REGISTRY)
