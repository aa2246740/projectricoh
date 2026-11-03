#!/usr/bin/env python3
"""Project available relative references into firmware controls; never emit a DAT."""
import csv
import hashlib
import json
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
COLORS = ['orange', 'green', 'blue', 'red', 'magenta']
RAW = [7, 6, 1, 2, 3, 4, 5, 8, 9]


def main():
    catalog_path = ROOT / 'research/color_targets/targets.json'
    catalog = json.loads(catalog_path.read_text())
    firmware = json.loads((HERE / 'firmware_parameters.json').read_text())
    references = json.loads((HERE / 'reference_analysis.json').read_text())['relative_mappings']
    x = np.linspace(0, 1, 2049)

    def curve(row):
        c = firmware['curves'][row - 1]
        return np.interp(x, np.array(c['candidate_x']) / 4095, np.array(c['output_u8']) / 255)

    baseline = curve(firmware['ordinary_contrast_selectors'][4]['lut_id'])
    all_curves = np.array([curve(s['lut_id']) for s in firmware['ordinary_contrast_selectors']])
    results = []
    for target in catalog['targets']:
        tid = target['id']
        r = {'slot': target['proposed_slot'], 'id': tid, 'official_mode': target['official_mode'],
             'output_kind': target['output_kind'], 'official_source': target['source'],
             'gxr_parameters': None, 'gxr_match_measurement': None,
             'camera_calibrated': False, 'deployable': False, 'research_seed': None,
             'brand_match_95pct_interval': None}
        if tid in references:
            ref = references[tid]
            params = {'contrast': 5, 'sharpness': 5, 'vividness': 5}
            color_fit = []
            for i, group in enumerate(ref['groups']):
                desired = group['median_chroma_ratio']
                sectors = firmware['color_masks'][i]['sectors']
                k = np.array([np.median(np.array(a)[sectors]) / 100
                              for a in firmware['normal_sector_saturation_k_percent']])
                selected = int(np.argmin(np.abs(k - desired))) + 1 if desired is not None else 5
                params[COLORS[i] + '_saturation'] = selected
                color_fit.append({'color': COLORS[i], 'reference_patches': group['n'],
                                  'reference_chroma_ratio_median': desired,
                                  'reference_ratio_min_max': group['observed_ratio_min_max'],
                                  'firmware_coefficient_ratio': float(k[selected - 1]),
                                  'display': selected,
                                  'outside_coefficient_range': bool(desired is not None and not k.min() <= desired <= k.max()),
                                  'reference_hue_shift_degrees_unimplemented': group['median_hue_shift_degrees']})
            for color in COLORS:
                params[color + '_hue'] = 5
            tone_fit = None
            if tid.startswith('ricoh_gr3_'):
                ref_x = np.array(ref['tone_input_encoded_luma'])
                ref_y = np.array(ref['tone_output_encoded_luma'])
                in_domain = (baseline >= ref_x.min()) & (baseline <= ref_x.max())
                ideal = np.interp(baseline[in_domain], ref_x, ref_y)
                errors = np.sqrt(np.mean((all_curves[:, in_domain] - ideal) ** 2, axis=1)) * 255
                params['contrast'] = int(errors.argmin()) + 1
                tone_fit = {'selected_display': params['contrast'], 'lut_id': params['contrast'],
                            'lut_output_code_rmse_by_display_1_to_9': errors.tolist(),
                            'input_grid_points_used': int(in_domain.sum()), 'input_grid_points_total': len(x),
                            'scope': 'conditional 1D firmware-node model fit to measured GR III Standard-relative neutral transfer',
                            'assumptions': ['GXR LUT X/Y are input/output nodes with linear interpolation',
                                            'GXR middle row is used as an abstract neutral baseline, not measured Standard',
                                            'GR III encoded relative tone transform transfers to the GXR LUT output domain'],
                            'gxr_pixel_error': None}
            r.update(status='REFERENCE_QUANTIFIED_FIRMWARE_PROJECTION_ONLY',
                     reference_kind=ref['source_kind'], reference_limits=ref['limits'],
                     research_seed={'display_13': params,
                                    'raw_13': [RAW[params[k] - 1] for k in params],
                                    'wb_axes': [0, 0], 'requested_selector': '0x04',
                                    'color_projection': color_fit, 'tone_projection': tone_fit,
                                    'frozen_controls': ['sharpness', 'global vividness', 'all hue controls', 'both WB axes']
                                                       + (['contrast: reference working-space domain incompatible'] if tid.startswith('fuji_') else []),
                                    'confidence': {'camera_effect': 'unmeasured', 'brand_equivalence': 'unmeasured',
                                                   'statistical_interval': None,
                                                   'unconstrained_control_domains_not_confidence_intervals': {
                                                       'hue_each': [1, 9], 'wb_each': [-8, 8]},
                                                   'why_no_interval': 'no GXR chromatic chart or parameter deltas; reference patch spread is scene variation, not estimator uncertainty'}})
        elif target['output_kind'] == 'monochrome':
            r.update(status='BLOCKED_CURRENT_RECIPE_HAS_NO_MONOCHROME_MODE',
                     required_before_fit=['real monochrome processing and selector support',
                                          'reference and GXR grayscale/color-filter response pairs'],
                     reason='Current recipes force 0x04 color Setting1; saturation minimum is not a monochrome path.')
        else:
            r.update(status='OFFICIAL_QUALITATIVE_REFERENCE_ONLY_NO_NUMERIC_FIT',
                     reason='No paired numeric target acquired for this exact camera/mode; do not invent slider values or borrow a different generation.')
        results.append(r)
    output = {'schema': 'gxr-research-projections-not-installable-v1',
              'status': 'PARTIAL_REFERENCE_ANALYSIS_NOT_16_CAMERA_CALIBRATIONS',
              'catalog_sha256': hashlib.sha256(catalog_path.read_bytes()).hexdigest(),
              'source_reference_file': 'reference_analysis.json',
              'source_firmware_file': 'firmware_parameters.json',
              'camera_calibrated_count': 0, 'targets': results,
              'projection_definition': 'Per-group Lab chroma ratios are projected onto exact ISP coefficient k steps, assuming those ratios transfer. Hue and WB are frozen. This assumption has no GXR chromatic validation.',
              'ready_for_recipe_library': False,
              'missing_to_claim_calibration': ['controlled GXR chart at baseline and independent parameter changes',
                                               'GXR color/illumination forward model',
                                               'complete numeric references for remaining targets',
                                               'held-out scenes/illuminants and real camera JPEG+DNG acceptance']}
    (HERE / 'target_parameter_projections.json').write_text(json.dumps(output, indent=2, ensure_ascii=False, allow_nan=False) + '\n')
    with (HERE / 'target_status.csv').open('w') as f:
        w = csv.writer(f)
        w.writerow(['slot', 'id', 'status', 'contrast', 'sharpness', 'vividness', *[c + '_saturation' for c in COLORS],
                    *[c + '_hue' for c in COLORS], 'wb0', 'wb1', 'camera_calibrated', 'deployable'])
        for r in results:
            params = r['research_seed']['display_13'] if r['research_seed'] else {}
            w.writerow([r['slot'], r['id'], r['status'], *params.values(), *([''] * (13 - len(params))),
                        *(r['research_seed']['wb_axes'] if r['research_seed'] else ['', '']), False, False])
    print(json.dumps({'targets': len(results), 'reference_based_research_seeds': sum(r['research_seed'] is not None for r in results),
                      'camera_calibrated': 0, 'deployable': 0}))


if __name__ == '__main__':
    main()
