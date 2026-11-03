#!/usr/bin/env python3
"""Small real-DNG boundary tests, writing only to a fresh private fixture."""
import sys
from pathlib import Path
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import onboard
import native as n
import owners
import instructions_r3
from unittest.mock import patch
import argparse


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scratch', type=Path, required=True)
    args = parser.parse_args()
    n.preflight()
    folder = owners.private_path(args.scratch)
    folder.mkdir(parents=True, exist_ok=False)
    source = n.ROOT / owners.get('gr4hdf')['template']['path']
    original = source.read_bytes()
    tiff = n.Tiff(original)
    checks = []

    def inspect_variant(name, mutate, reason):
        data = bytearray(original)
        mutate(data)
        destination = n.output(folder / 'captures/contrib' / f'{name}.DNG')
        destination.write_bytes(data)
        with patch.object(n, 'ROOT', folder):
            row = onboard.inspect(destination)
        n.require(not row['eligible'] and any(reason in value for value in row['reasons']),
                  f'{name} accepted, or wrong plain reason: {row["reasons"]}')
        checks.append(dict(name=name, passed=True, reasons=row['reasons']))

    inspect_variant('portrait', lambda data: n.write_uint(data, tiff.root.entries[274], 0, 6),
                    'portrait orientation')
    inspect_variant('crop', lambda data: n.write_uint(data, tiff.raw.entries[50720], 0, 4096),
                    'not 6192x4128')
    inspect_variant('black-level', lambda data: n.write_uint(data, tiff.raw.entries[50714], 0, 65),
                    'unsupported RAW geometry')

    rows = onboard.candidates([
        n.ROOT / 'captures/contrib/2026-10-22-gr4hdf-screenchart/dng/1792597588000_R0003038.DNG',
        n.ROOT / 'captures/contrib/2026-10-22-gr4hdf-screenchart/dng/1792597571000_R0003037.DNG'])
    selected, _ = onboard.choose(rows)
    n.require(selected['path'].endswith('R0003038.DNG') and rows[1]['warnings'] and
              not rows[1]['eligible'] and rows[1]['geometry']['black'] == [256]*4,
              'eligible-template selection or actual ISO-640 black-level exclusion changed')
    checks.append(dict(name='real-candidate-iso-640-black-256-excluded', passed=True))
    data = bytearray(original)
    iso_entry = next(node.entries[34855] for node in tiff.ifds if 34855 in node.entries)
    n.write_uint(data, iso_entry, 0, 640)
    high_iso = n.output(folder / 'captures/contrib/high-iso-black-64.DNG')
    high_iso.write_bytes(data)
    with patch.object(n, 'ROOT', folder):
        high_iso_row = onboard.inspect(high_iso)
    n.require(high_iso_row['eligible'] and high_iso_row['warnings'],
              'high ISO alone must not refuse an otherwise eligible template')
    checks.append(dict(name='high-iso-alone-allowed-and-flagged', passed=True))
    # Mutate the existing camera's contrast slider, keeping ISO and allocation identical.
    data = bytearray(original)
    control = tiff.maker().entries[0x0247]
    data[control.offset+6:control.offset+8] = (4).to_bytes(2, 'little', signed=True)
    modified = n.output(folder / 'captures/contrib/modified-preset.DNG')
    modified.write_bytes(data)
    with patch.object(n, 'ROOT', folder):
        modified_row = onboard.inspect(modified)
    default_row = onboard.inspect(source)
    n.require(onboard.choose([modified_row, default_row])[0]['path'] == str(source.relative_to(n.ROOT)),
              'factory-default tie preference changed')
    checks.append(dict(name='factory-default-tie', passed=True))
    custom = dict(model='RICOH GR IV', instructions=dict(control_label_zh='自定义对照句。',
                                                       control_label_en='Custom control sentence.'))
    with patch.object(owners, 'get', return_value=custom):
        text = instructions_r3.text('new-owner')
        n.require('自定义对照句。' in text and 'Custom control sentence.' in text and
                  'HDF' not in text and 'R09000' not in text, 'custom labels/new plain-GR-IV text differ')
    checks.append(dict(name='plain-gr4-labels-and-no-old-files', passed=True))
    for owner, entry in owners.load().items():
        if entry.get('regression_sha256'):
            n.require(n.digest(instructions_r3.text(owner).encode()) ==
                      entry['regression_sha256']['OWNER_ZH_EN.txt'], 'canonical handout regression')
    checks.append(dict(name='two-canonical-handouts', passed=True))

    # Inject one byte of damage AFTER a real round trip, at the full-preview DQT header.
    # The proof must report that exact stream/segment and must not produce a passed proof.
    n.SCRATCH = folder / 'codec'
    n.preflight()
    n.compile_codec()
    owners.set_root('gr4hdf', owners.PRIVATE / 'gr4hdf' / folder.name)
    proof_root = owners.root('gr4hdf')
    n.require(not proof_root.exists(), 'fresh proof-failure directory required')
    real_run = n.run
    def damaged(*arguments):
        real_run(*arguments)
        if arguments[0] == 'jpeg-roundtrip' and Path(arguments[1]).name == 'full.original.jpg':
            target = Path(arguments[2])
            data = bytearray(target.read_bytes())
            data[10] ^= 1
            target.write_bytes(data)
    with patch.object(n, 'run', side_effect=damaged):
        try:
            n.prove('gr4hdf')
        except ValueError as error:
            n.require('G2 gr4hdf/full' in str(error) and 'FFDB' in str(error) and 'STOP' in str(error),
                      f'proof failed without the precise stream/header: {error}')
            failure = n.read(proof_root / 'r3/proof/failure.json')
            n.require(failure['stream'] == 'full' and failure['gate'] == 'G2' and
                      failure['original_header']['sha256'] != failure['roundtrip_header']['sha256'] and
                      not (proof_root / 'r3/proof/proof.json').exists() and
                      not (proof_root / 'cards').exists(), 'failed proof generated downstream artifacts')
            checks.append(dict(name='g2-header-stop', passed=True, message=str(error), evidence=failure))
        else:
            raise ValueError('damaged full-preview header accepted')
    n.dump(folder / 'tests.json', dict(passed=True, checks=checks))
    print(f'{len(checks)} boundary checks PASS; {folder / "tests.json"}')


if __name__ == '__main__':
    main()
