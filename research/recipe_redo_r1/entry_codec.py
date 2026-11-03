"""Serialize standalone 552-byte research records, never a DAT or firmware."""
from pathlib import Path
import struct
import zlib
import runtime as rt
from runtime import np
from gxr_studio.camdata.datcodec import CRC_FIELDS, OFFSETS, ROW_BYTES, _valid_look_row
from gxr_studio.engine.knobs import dec


def predict(entry, x, ui, *, half=0, round_output=True):
    """Always execute the Standard colour chain; no slot-03 grayscale shortcut."""
    model = rt.camera_model(ui)
    pre = model.pre(entry, np.asarray(x))
    row = rt.mm.MatrixRow.from_bytes(entry[216+half*28:244+half*28])
    coeff = np.array([[dec(z, 128) for z in entry[i:i+4]] for i in range(115, 211, 4)])
    assert np.array_equal(coeff[:, 0], coeff[:, 3]) and np.array_equal(coeff[:, 1], -coeff[:, 2])
    z = rt.fs.Z_of_words(coeff[:, 0], coeff[:, 1], model.engine.ctx)
    y, ci = row.apply(pre)
    co = model.engine.table.forward(ci, z)[0]
    out = np.clip(rt.mm.rgb_from_ycc(y, co), 0, 255)
    return np.rint(out) if round_output else out


def encode_signed_byte(value):
    value = int(value)
    assert abs(value) <= 127
    return 128 + abs(value) if value < 0 else value


def encode(template, parameters, *, level, gray=False, identity=None, mirror_iso100=True, look_unit_mask=None):
    assert len(template) == 552 and level in (0, 1)
    entry = bytearray(template)
    if identity is not None:
        entry[4:8] = bytes(identity)
    entry[1] = (entry[1] & ~6) | (6 if level == 1 else 0)
    entry[445:447] = struct.pack('>H', 0 if level == 1 else 2)
    nodes = np.asarray(parameters['curve_x_u12'], int)
    assert nodes.shape == (33,) and nodes[0] == 0 and nodes[-1] == 4095 and (np.diff(nodes) > 0).all()
    entry[20:82] = struct.pack('>31H', *nodes[1:-1])
    curves = np.asarray(parameters['curve_y_u8'], int)
    if len(curves) == 1:
        curves = np.repeat(curves, 3, axis=0)
    assert curves.shape == (3, 33) and (curves >= 0).all() and (curves <= 255).all()
    assert (np.diff(curves, axis=1) >= 0).all()
    entry[82:115] = bytes(curves[1].tolist())
    if level == 1:
        entry[379:412] = bytes(curves[0].tolist())
        entry[412:445] = bytes(curves[2].tolist())
    if mirror_iso100:
        entry[456:518] = entry[20:82]
        entry[518:551] = entry[82:115]
    original = rt.mm.MatrixRow.from_bytes(template[216:244])
    matrix = np.asarray(parameters['matrix_q10'], int).copy()
    if gray:
        # Standard remains a colour mode. Zero physical chroma coefficients,
        # rather than relying on a model or native B&W selector to remove it.
        matrix[1:] = 0
    entry[216:244] = rt.mm.MatrixRow(matrix, original.tail).to_bytes()
    second = rt.mm.MatrixRow.from_bytes(template[244:272])
    if gray:
        second_coef = second.coef.copy()
        second_coef[1:] = 0
        entry[244:272] = rt.mm.MatrixRow(second_coef, second.tail).to_bytes()
    if gray:
        entry[115:211] = bytes(96)
    else:
        a, b = np.asarray(parameters['sector_a'], int), np.asarray(parameters['sector_b'], int)
        entry[115:211] = b''.join(rt.fs.encode_word(aa, bb) for aa, bb in zip(a, b))
    if look_unit_mask is not None:
        assert 1 <= look_unit_mask <= 7 and identity is None
        content = bytes(entry[:2])+bytes(entry[445:447])+bytes((look_unit_mask,))
        content += b''.join(entry[off:off+n] for off, n in zip(OFFSETS, ROW_BYTES))
        entry[4:8] = struct.pack('>I', zlib.crc32(content) & 0xffffffff)
    for off, size, crc_off in CRC_FIELDS:
        struct.pack_into('>I', entry, crc_off, zlib.crc32(entry[off:off+size]) & 0xffffffff)
    assert len(entry) == 552
    assert all(_valid_look_row(bytes(entry[off:off+n]), ordinal, entry[1])
               for ordinal, (off, n) in enumerate(zip(OFFSETS, ROW_BYTES))), 'Record fails existing row-domain checks'
    for off, size, crc_off in CRC_FIELDS:
        assert struct.unpack_from('>I', entry, crc_off)[0] == zlib.crc32(entry[off:off+size]) & 0xffffffff
    return bytes(entry)


def record_checks(entry):
    assert len(entry) == 552
    return dict(bytes=552, sha256=__import__('hashlib').sha256(entry).hexdigest(),
        row_crc_count=len(CRC_FIELDS), row_crcs_valid=all(struct.unpack_from('>I', entry, co)[0] == zlib.crc32(entry[off:off+n]) & 0xffffffff
            for off, n, co in CRC_FIELDS), independent_curves=bool(entry[1] & 4),
        existing_row_domain_checks_pass=all(_valid_look_row(entry[off:off+n], ordinal, entry[1])
            for ordinal, (off, n) in enumerate(zip(OFFSETS, ROW_BYTES))),
        type26_control=struct.unpack_from('>H', entry, 445)[0],
        no_dat_or_firmware_output=True)


def look_identity_valid(entry, unit_mask):
    content = entry[:2]+entry[445:447]+bytes((unit_mask,))
    content += b''.join(entry[off:off+n] for off, n in zip(OFFSETS, ROW_BYTES))
    return struct.unpack_from('>I', entry, 4)[0] == zlib.crc32(content) & 0xffffffff
