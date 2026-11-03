"""Explicit numerical hypotheses for the static Ricoh pipeline study.

No camera, package generation, or firmware modification. Import with -I -B.
"""
import sys
sys.dont_write_bytecode = True
import hashlib
import struct
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from colour_math_frozen import delta_e00, rgb_lab, srgb_decode

RGB_LUMA = np.array([77, 150, 29], dtype=float) / 256
YCC = np.array([[77, 150, 29], [-43, -85, 128], [128, -107, -21]], dtype=float) / 256


def pack_record(values, scalar, endian='>'):
    values = np.asarray(values).reshape(-1).tolist()
    raw = struct.pack(endian + scalar * len(values), *values)
    return {'values': values, 'hex': raw.hex(), 'bytes': len(raw),
            'sha256': hashlib.sha256(raw).hexdigest()}


def compose_q13(left, right):
    """MMUL16: signed16 operands, +4096, arithmetic >>13, low signed16."""
    value = (np.asarray(left, dtype=np.int64).reshape(3, 3)
             @ np.asarray(right, dtype=np.int64).reshape(3, 3) + 4096) >> 13
    return ((value + 32768) % 65536 - 32768).astype(np.int64)


def compose_q13_i32(left, right):
    """MMUL32: signed products, +4096, signed division truncates toward zero."""
    value = (np.asarray(left, dtype=np.int64).reshape(3, 3)
             @ np.asarray(right, dtype=np.int64).reshape(3, 3) + 4096)
    return np.where(value < 0, -((-value) // 8192), value // 8192)


def front_q8(composed, gain_scalar=128):
    """Observed ColorMatrix Calc default-branch matrix quantization.

    The integer values are static. Q8 as the pixel interpretation is an inference
    from the 256 row sums and the explicit gain state, not a chip specification.
    """
    value = np.asarray(composed, dtype=np.int64).reshape(3, 3) * gain_scalar
    value = np.where(value < 0, -((-value) // 4096), value // 4096)
    for i in range(3):
        value[i, i] = 2 * gain_scalar - sum(value[i, j] for j in range(3) if i != j)
    return np.clip(value, -2048, 2047)


def metrics(prediction, actual, neutral=None):
    prediction = np.asarray(prediction, dtype=float)
    actual = np.asarray(actual, dtype=float)
    lab_prediction = rgb_lab(np.clip(prediction, 0, 1))
    lab_actual = rgb_lab(actual)
    de = delta_e00(lab_prediction, lab_actual)
    encoded_luma_error = (prediction - actual) @ RGB_LUMA * 255
    linear_y_error = ((srgb_decode(np.clip(prediction, 0, 1)) - srgb_decode(actual))
                      @ np.array([.2126729, .7151522, .0721750]))
    lightness_error = lab_prediction[:, 0] - lab_actual[:, 0]
    result = {
        'patch_count': len(de), 'de00_median': float(np.median(de)),
        'de00_p90': float(np.percentile(de, 90)), 'de00_max': float(np.max(de)),
        'encoded_luma8_signed_mean': float(np.mean(encoded_luma_error)),
        'encoded_luma8_mae': float(np.mean(np.abs(encoded_luma_error))),
        'encoded_luma8_rmse': float(np.sqrt(np.mean(encoded_luma_error ** 2))),
        'encoded_luma8_p90_absolute': float(np.percentile(np.abs(encoded_luma_error), 90)),
        'linear_srgb_Y_mae': float(np.mean(np.abs(linear_y_error))),
        'Lab_Lstar_mae': float(np.mean(np.abs(lightness_error))),
        'per_patch': [dict(de00=float(d), encoded_luma8_residual=float(y),
                           linear_srgb_Y_residual=float(ly), Lstar_residual=float(L))
                      for d, y, ly, L in zip(de, encoded_luma_error, linear_y_error, lightness_error)],
    }
    if neutral is not None:
        neutral = np.asarray(neutral, dtype=bool)
        result['neutral_6'] = metrics(prediction[neutral], actual[neutral])
        result['coloured_18'] = metrics(prediction[~neutral], actual[~neutral])
    return result


def curve_lookup(curve, input_u12):
    """Hypothesis: 256 knots at x=16*k; upper 15 input codes clamp to last."""
    return np.interp(input_u12, np.arange(256) * 16, np.asarray(curve, dtype=float))


def project_curve(curve, output_bits=8, adaptive=True):
    """33-node linear-interpolation projection, independently checkable on 4096 codes.

    The inferred GXR abscissa/endpoints are hypotheses, not silicon semantics.
    Nodes are chosen by a deterministic largest-error split; rounding is to even.
    """
    dense_x = np.arange(4096)
    curve = np.asarray(curve, dtype=float)
    dense = np.clip(curve_lookup(curve, dense_x) / 16384, 0, 1)
    if adaptive:
        nodes = [0, 4095]
        for _ in range(31):
            interp = np.interp(dense_x, nodes, dense[nodes])
            error = np.abs(dense - interp)
            error[nodes] = -1
            nodes = sorted(nodes + [int(np.argmax(error))])
    else:
        nodes = [0] + list(range(128, 3969, 128)) + [4095]
    nodes = np.asarray(nodes, dtype=int)
    maximum = 2 ** output_bits - 1
    values = np.rint(dense[nodes] * maximum).astype(int)
    reconstruct = np.interp(dense_x, nodes, values) / maximum
    error8 = (reconstruct - dense) * 255
    return {
        'evidence_level': '推断', 'source_output_scale': 16384,
        'source_x_knots_u12': '16*k for k=0..255; final interval clamped',
        'destination_abscissa_semantics': '31 internal nodes plus inferred endpoints 0,4095; linear interpolation assumed',
        'node_strategy': 'greedy largest floating interpolation error, 31 deterministic splits' if adaptive else 'stock GXR equal-spaced input row 19',
        'input31_u16BE': pack_record(nodes[1:-1], 'H'),
        'output33': pack_record(values, 'B' if output_bits == 8 else 'H'),
        'output_bits': output_bits,
        'dense_4096_error_in_rgb8_codes': {
            'max_absolute': float(np.max(np.abs(error8))),
            'p90_absolute': float(np.percentile(np.abs(error8), 90)),
            'rmse': float(np.sqrt(np.mean(error8 ** 2)))},
        'strictly_increasing_x': bool(np.all(np.diff(nodes) > 0)),
        'nondecreasing_y': bool(np.all(np.diff(values) >= 0)),
    }


def sign_magnitude(values, scale, sign_bit):
    quantized = np.rint(np.asarray(values, dtype=float) * scale).astype(np.int64)
    limit = sign_bit - 1
    if np.any(np.abs(quantized) > limit):
        raise ValueError('coefficient exceeds proposed sign-magnitude range')
    encoded = np.abs(quantized) | np.where(quantized < 0, sign_bit, 0)
    return quantized, encoded


def project_matrix(matrix):
    matrix = np.asarray(matrix, dtype=float).reshape(3, 3)
    q, raw = sign_magnitude(matrix, 1024, 0x800)
    source = np.r_[raw.ravel(), [0, 0, 0, 0, 0]]
    # Exact software packer mapping; semantic interpretation remains inferred.
    words = [(int(raw.ravel()[i]) << 16) | int(raw.ravel()[i + 1])
             for i in range(0, 8, 2)]
    words += [int(raw.ravel()[8]), 0, 0, 0]
    error = q / 1024 - matrix
    return {
        'evidence_level': '推断',
        'format_assumption': 'Q10, sign magnitude bit11, amplitude<=2047',
        'matrix_float_row_major': matrix.reshape(-1).tolist(),
        'matrix_signed_q10': q.reshape(-1).tolist(),
        'source14_u16BE': pack_record(source, 'H'),
        'register8_u32BE_C100_to_C11C': pack_record(words, 'I'),
        'quantization_max_absolute_coefficient': float(np.max(np.abs(error))),
        'quantization_max_unit_cube_output_error': float(np.max(np.sum(np.abs(error), axis=1))),
        'quantized_row_sums': np.sum(q, axis=1).tolist(),
        'hardware_stage_is_linear_raw_rgb': '未知',
        'activation_control_words': None,
    }


def project_chroma_similarity(matrix):
    """Fit the 2x2 chroma submatrix by [[a,b],[-b,a]], repeated in 24 slots.

    This is a deliberately limited candidate, not a recovered GR/GXR sector map.
    A global linear look has one chroma submatrix: fabricating hue-dependent data
    would add unsupported parameters. The GR IV MultiAxial is not approximated.
    """
    matrix = np.asarray(matrix, dtype=float).reshape(3, 3)
    transformed = YCC @ matrix @ np.linalg.inv(YCC)
    chroma = transformed[1:, 1:]
    a = (chroma[0, 0] + chroma[1, 1]) / 2
    b = (chroma[0, 1] - chroma[1, 0]) / 2
    q, encoded = sign_magnitude([a, b], 32, 0x80)
    A, B = map(int, encoded)
    word = (A << 24) | (B << 16) | ((B ^ 0x80) << 8) | A
    projected = np.array([[q[0], q[1]], [-q[1], q[0]]], dtype=float) / 32
    return {
        'evidence_level': '推断',
        'role': 'alternative partial chroma-only carrier; do not combine with the full look matrix',
        'source_is_only_q13_look_matrix': True,
        'includes_GR4_multiaxial': False,
        'does_not_depend_on_unconfirmed_sector_angles': True,
        'all_24_slots_identical_because_source_transform_is_global': True,
        'YCC_basis_assumption': YCC.tolist(),
        'look_in_YCC_basis': transformed.tolist(),
        'ideal_similarity_ab': [float(a), float(b)],
        'quantized_similarity_ab_q5': q.tolist(),
        'sector24_u32BE': pack_record([word] * 24, 'I'),
        'chroma_submatrix_frobenius_error': float(np.linalg.norm(chroma - projected)),
        'omitted_luma_row_and_chroma_from_luma': [transformed[0, :].tolist(), transformed[1:, 0].tolist()],
        'exact_semantic_projection': False,
        'destination_boundaries_and_tail_gain_tables': None,
        'activation_control_words': None,
    }
