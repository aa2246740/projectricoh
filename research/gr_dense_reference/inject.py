#!/usr/bin/env python3
"""Build the public-container set using the original in-place injector unchanged."""
import sys
from pathlib import Path
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import dense
common = dense.legacy()
import importlib.util
import lattice
import owners


def injector():
    path = common.pin(dense.ROOT / 'research/gr_incamera_dev/inject.py')
    spec = importlib.util.spec_from_file_location('gr_dense_legacy_inject', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.raw_mosaic = lattice.mosaic
    return module


def build(band=None, acceptance=False, template=None, private_owner=None):
    dense.require((dense.HERE / 'local/protected.json').exists(), 'capture read-only baseline first')
    public = template is None
    dense.require(private_owner is None or not public, '--private-owner requires --private-template')
    if private_owner is not None:
        entry = owners.get(private_owner)
        dense.require(Path(template).resolve() == (owners.ROOT / entry['template']['path']).resolve()
                      and dense.sha(template) == entry['template']['sha256'], 'private owner template differs')
    template = common.GR3 if public else Path(template).resolve()
    dense.require(public or template.is_relative_to(dense.ROOT), 'template outside checkout')
    name = 'R0900001' if acceptance else f'R090000{band + 2}'
    if public:
        destination = dense.delivery() / f'{name}.DNG'
        private_local = common.LOCAL
    else:
        private_local = dense.HERE / 'local/private'
        if private_owner:
            private_local = owners.root(private_owner)
        else:
            name = 'PRIVATE_acceptance' if acceptance else f'PRIVATE_band{band + 1}'
        destination = private_local / f'{name}.DNG'
    module = injector()
    # Per-patch manifests stay with the owner; the shared codec TMP remains under local/tmp.
    module.LOCAL = private_local
    module.design = lambda tiff, kind: lattice.design(tiff, band or 0, acceptance)
    manifest = module.inject(template, 'colour', destination, 'same-owner', 'replace')
    card = dense.read(manifest)
    card.update(public_container=public, public_source='bastibe GR III 1.60' if public else None,
                shareable_data_file=public, develop_styles=['standard', 'positive', 'negative'],
                one_raw_developed_three_times=True)
    dense.dump(manifest, card)
    print(f'{destination.relative_to(dense.ROOT)}  patches={len(card["patches"])}  sha256={card["dng_sha256"]}')
    return manifest


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--acceptance', action='store_true')
    group.add_argument('--band', type=int, choices=range(1, 5))
    parser.add_argument('--private-template', type=Path,
                        help='same-owner variant; always local/private; never public')
    parser.add_argument('--private-owner', choices=tuple(owners.templates()),
                        help='isolate this owner under local/private and use camera filenames')
    args = parser.parse_args()
    build(None if args.band is None else args.band - 1, args.acceptance,
          args.private_template, args.private_owner)
