#!/usr/bin/env python3
"""Median dE00 between looks on the shared synthetic holdout (how different the candidates are from each other)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from guard import HERE, mount_guard, install_write_fence, dump


def main():
    mount_guard(); install_write_fence()
    import numpy as np
    from camera import Camera
    from convert import prepare, samples, DEFAULT_SCENES
    from cube import Cube
    from spaces import Target
    from engines_ceiling import USER, USER_CUBES, HF, HF_LUTS, read_lut16
    camera = Camera()
    ref = prepare(camera, DEFAULT_SCENES[:1], 280)[0]
    x, _ = samples(camera, 1400, 20261023)
    stock = camera.stock(x)
    xyz = camera.xyz(x, ref['neutral'], ref['matrix'])
    looks = {'04': stock}
    for n in USER_CUBES:
        looks[n.replace('_33_Rec709', '')] = Target(Cube.read(str(USER/f'{n}.cube')), 'srgb').render(stock, xyz)
    for code, stock_name in HF_LUTS.items():
        looks[stock_name] = Target(read_lut16(HF/f'olut_{code}_sk.lut16'), 'srgb').render(stock, xyz)
    lab = {k: camera.fs.lab_from_codes(v) for k, v in looks.items()}
    names = list(looks)
    m = {a: {b: float(np.median(camera.fs.delta_e00(lab[a], lab[b]))) for b in names} for a in names}
    dump(HERE/'local/pairwise.json', m)
    print('median dE00 on synthetic holdout')
    print(' '*34 + ' '.join(f'{n[:7]:>7s}' for n in names))
    for a in names:
        print(f'{a[:33]:33s} ' + ' '.join(f'{m[a][b]:7.2f}' for b in names))


if __name__ == '__main__':
    main()
