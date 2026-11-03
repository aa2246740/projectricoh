"""A channel-wise smooth field from rotating chart anchors, not a lens profile."""
import copy
import runtime as rt
from runtime import np
from scipy.optimize import least_squares


def basis(xy):
    x, y = np.asarray(xy).T
    return np.column_stack((x, y, x*x, x*y, y*y))


def position(row, geometry):
    p = next(p for p in geometry[row['frame']]['patches'] if p['patch_id'] == row['patch_id'])
    xy = np.mean(p['roi_polygon'], axis=0)
    return (xy - [2144, 1424]) / [2144, 1424]


def fit(rows, geometry, exclude_page=None):
    anchors = [r for r in rows if r['class'] == 'anchor' and r['page'] != exclude_page
        and np.min(r['raw_rgb']) > .003 and np.max(r['raw_rgb']) < .97
        and np.max(r['spatial_sd']['raw_rgb']) < .025]
    names = sorted({r['sample_key'] for r in anchors})
    frames = sorted({r['frame'] for r in anchors})
    xy = np.array([position(r, geometry) for r in anchors])
    spatial = basis(xy)
    colors = np.array([[r['sample_key'] == name for name in names] for r in anchors], float)
    exposure = np.array([[r['frame'] == name for name in frames[1:]] for r in anchors], float)
    H = np.column_stack((colors, exposure, spatial))
    target = np.log(np.array([r['raw_rgb'] for r in anchors]))
    assert np.linalg.matrix_rank(H) == H.shape[1], 'spatial field not identifiable from anchors'
    coef = []
    for ch in range(3):
        initial = np.linalg.lstsq(H, target[:, ch], rcond=None)[0]
        opt = least_squares(lambda c: np.r_[(H @ c-target[:,ch])/.025, c[-5:]*.6],
            initial, loss='soft_l1', max_nfev=60)
        coef.append(opt.x)
    coef = np.array(coef).T
    residual = H @ coef-target
    return {'schema': 'mount-spatial-field/1', 'exclude_page': exclude_page,
        'coefficients_log_rgb': coef[-5:].tolist(), 'n_anchors': len(anchors),
        'rank': int(np.linalg.matrix_rank(H)), 'parameters': H.shape[1],
        'basis': ['x', 'y', 'x2', 'xy', 'y2'], 'center_px': [2144,1424], 'scale_px': [2144,1424],
        'training_anchor_keys': [[r['frame'],r['patch_id']] for r in anchors],
        'rms_log_rgb': np.sqrt(np.mean(residual**2, axis=0)).tolist(),
        'support_normalized_xy': [xy.min(axis=0).tolist(),xy.max(axis=0).tolist()],
        'frame_log_rgb': {frames[0]: [0,0,0], **{f: coef[len(names)+i].tolist() for i,f in enumerate(frames[1:])}},
        'anchor_center_log_rgb': {name: coef[i].tolist() for i,name in enumerate(names)},
        'interpretation': 'combined screen, viewing angle and lens field; no isolated lens attribution; center value constrained to one'}


def gains(field, xy):
    return np.exp(-basis(np.asarray(xy)) @ np.array(field['coefficients_log_rgb']))


def standardize(rows, geometry, field, model, latent, bad):
    result = copy.deepcopy(rows)
    xy = np.array([position(r, geometry) for r in rows])
    gain = gains(field, xy)
    corrected_jpeg = model.predict('04', latent*gain)
    for i, r in enumerate(result):
        r['original_raw_rgb'] = r['raw_rgb']
        r['original_jpeg_rgb'] = r['jpeg_rgb']
        r['spatial_gain_rgb'] = gain[i].tolist()
        r['spatial_xy'] = xy[i].tolist()
        r['raw_rgb'] = (np.array(r['raw_rgb'])*gain[i]).tolist()
        r['spatial_sd']['raw_rgb'] = (np.array(r['spatial_sd']['raw_rgb'])*gain[i]).tolist()
        if r['valid']:
            r['jpeg_rgb'] = corrected_jpeg[i].tolist()
            if bad[i] or np.max(r['raw_rgb']) >= .98 or np.min(r['raw_rgb']) < 0:
                r['valid'] = False
                r['flags'].append('spatial-standardization-or-04-inverse-rejected')
    return result
