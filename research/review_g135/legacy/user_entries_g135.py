"""Review copy of firmware/engine_v52_redisplay/user_entries.py (only change: loads the gen 135 candidate/ui_data.py; the gen 135 tree ships no such tool)."""
import argparse
import hashlib
import importlib.util
from pathlib import Path
import json

spec = importlib.util.spec_from_file_location('ui_data', Path(__file__).resolve().parents[3] / 'firmware/engine_v53_g135/candidate/ui_data.py')
data = importlib.util.module_from_spec(spec)
spec.loader.exec_module(data)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('list', 'check', 'build'))
    parser.add_argument('dat', type=Path)
    parser.add_argument('--manifest', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    raw = args.dat.read_bytes()
    try:
        if args.command == 'build':
            if not args.manifest or not args.output:
                raise ValueError('build requires --manifest and --output')
            if args.output.resolve() == args.dat.resolve() or args.output.exists() or args.output.is_symlink():
                raise ValueError('output must be a new file, distinct from the input')
            if 'local' not in args.output.resolve().parts:
                raise ValueError('raw DAT output must be placed under a local directory')
            users = data.read_manifest(args.manifest.read_text())
            raw = data.replace_users(raw, users)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            with args.output.open('xb') as stream:
                stream.write(raw)
        _, ext, _, users = data.parse_dat(raw)
    except (ValueError, KeyError, TypeError, struct.error) as error:
        parser.exit(2, str(error) + '\n')
    entries = []
    for i, item in enumerate(users):
        at = data.USER_OFFSET + i*data.ENTRY_BYTES
        entries.append(dict(name=ext[at+2:at+10].split(b'\0')[0].decode('ascii'),
                            base=item['base'], levels=dict(zip(data.KEYS, item['levels']))))
    print(json.dumps(dict(status='PASS', entries=entries, count=len(entries),
                         capacity=data.CAPACITY, bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest()),
                     ensure_ascii=False, indent=2))

if __name__ == '__main__':
    import struct
    main()
