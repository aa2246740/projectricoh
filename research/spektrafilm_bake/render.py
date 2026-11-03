#!/usr/bin/env python3
"""spektrafilm side of the bake. Runs ONLY inside sandbox/run.sh with the Scratch venv, as `python -I`.

Self-contained on purpose (the sandbox can read this file but not the rest of the research tree).
Every input and output path is an argument; outputs go under the Scratch work tree.

  export  FILM OUTDIR       three 33^3 bundles with spektrafilm's own exporter (CLI for negatives;
                            BundleBuilder with io.scan_film for reversal stocks, as the GUI does):
                              srgb      sRGB in -> sRGB out, stops_above_midgray 'auto' (author default, +4.0)
                              srgbmid   sRGB in -> sRGB out, stops 2.4739 (gain 1.0: mid-grey not lifted)
                              vlog      V-Log/V-Gamut in -> sRGB out, 'auto' (native headroom, gain 1.0)
                              vlog65    the same at 65^3 (33^3 log-input interpolation is coarse in deep shadows)
  direct  FILM VARIANT IN.npy OUT.npy MODE
                            spektrafilm's runtime on an (H,W,3) image, without the LUT creator:
                              MODE pointwise : spatial + stochastic effects off, auto exposure off (lut_mode
                                               NOT set); input decoded with colour-science, the exporter's
                                               fixed linear gain applied, output encoded by the runtime.
                              MODE autoexp   : as pointwise but the runtime's default auto exposure on.
                              MODE spatial   : author defaults except grain and auto exposure off
                                               (halation, scatter, coupler diffusion, unsharp mask on).
  info                      versions, film list, default prints, gains (JSON on stdout)
"""
import json
import math
import sys
from pathlib import Path

import numpy as np

VARIANTS = {'srgb': ('sRGB', 'auto', 33), 'srgbmid': ('sRGB', math.log2(1 / 0.18), 33),
            'vlog': ('Panasonic V-Log', 'auto', 33), 'vlog65': ('Panasonic V-Log', 'auto', 65)}


def variant_def(variant):
    """Named variants above, or 'probe-<input slug>-<N>' (author-default exposure, N^3) for the log-input probe."""
    if variant in VARIANTS:
        return VARIANTS[variant]
    _, slug, n = variant.split('-')
    from spektrafilm_lut_creator import color_spaces
    return color_spaces.resolve(slug), 'auto', int(n)


def film_info(film):
    from spektrafilm.profiles.io import load_profile
    p = load_profile(film)
    return {'film': film, 'name': p.info.name, 'type': p.info.type, 'use': p.info.use,
            'target_print': p.info.target_print, 'positive': bool(p.is_positive)}


def print_for(info):
    # reversal stocks have no target print; the print profile is unused once scan_film is on
    return info['target_print'] or 'kodak_portra_endura'


def spec_for(film, variant):
    from spektrafilm_lut_creator.bundles import BundleSpec
    info = film_info(film)
    cs, stops, res = variant_def(variant)
    return info, BundleSpec(film_profile=film, print_profiles=(print_for(info),), input_color_space=cs,
                            output_color_space='sRGB', topology='1lut', resolution=res,
                            stops_above_midgray=stops, name=f'{film}_{variant}')


def cmd_export(film, outdir, variants=None):
    from spektrafilm_lut_creator import cli
    from spektrafilm_lut_creator.builders import BundleBuilder
    outdir = Path(outdir)
    done = {}
    for variant in (variants.split(',') if variants else VARIANTS):
        info, spec = spec_for(film, variant)
        if not info['positive']:
            argv = ['build', '--film', film, '--print', spec.print_profiles[0], '--input', spec.input_color_space,
                    '--output', 'sRGB', '--resolution', str(spec.resolution), '--name', spec.name, '--out', str(outdir)]
            if variant == 'srgbmid':
                # `--stops-above-gray` is parsed but never reaches the spec in v0.3.3 (argparse dest
                # stops_above_gray vs the override table's stops_above_midgray), so use the documented
                # `--from spec.toml` route for this one field.
                toml = outdir / f'{spec.name}.toml'
                toml.parent.mkdir(parents=True, exist_ok=True)
                toml.write_text(f'stops_above_midgray = {VARIANTS[variant][1]!r}\n')
                argv += ['--from', str(toml)]
            assert cli.main(argv) == 0
            how = 'spektrafilm-lut ' + ' '.join(argv)
        else:
            class ScanFilmBuilder(BundleBuilder):
                """The exporter's own builder; only io.scan_film follows the GUI rule (positive -> scan film)."""
                def _make_pipeline(self, spec, in_entry, out_entry, print_stock):
                    from spektrafilm.runtime.params_builder import digest_params, init_params
                    from spektrafilm.runtime.pipeline import SimulationPipeline
                    params = init_params(film_profile=spec.film_profile, print_profile=print_stock)
                    params.debug.lut_mode = True
                    params.io.input_color_space = in_entry.primaries
                    params.io.output_color_space = out_entry.primaries
                    params.io.input_cctf_decoding = False
                    params.io.output_cctf_encoding = False
                    params.io.input_gamut_compress = spec.input_gamut_compress
                    params.io.output_gamut_compress = spec.output_gamut_compress
                    params = digest_params(params)
                    params.io.scan_film = True
                    return SimulationPipeline(params)
            b = ScanFilmBuilder(spec)
            b.write(b.build(), outdir / spec.name)
            how = (f'BundleBuilder(BundleSpec(film_profile={film!r}, print_profiles=({spec.print_profiles[0]!r},), '
                   f'input_color_space={spec.input_color_space!r}, output_color_space="sRGB", resolution={spec.resolution}, '
                   f'stops_above_midgray={variant_def(variant)[1]!r})) with params.io.scan_film=True')
        done[variant] = {'dir': str(outdir / spec.name), 'how': how}
    print(json.dumps({'film': film, 'info': film_info(film), 'bundles': done}))


def direct_params(film, variant, mode):
    from spektrafilm.runtime.params_builder import digest_params, init_params
    from spektrafilm_lut_creator import color_spaces
    info, spec = spec_for(film, variant)
    entry = color_spaces.get(spec.input_color_space)
    params = init_params(film_profile=film, print_profile=spec.print_profiles[0])
    if mode in ('pointwise', 'autoexp'):
        params.debug.deactivate_spatial_effects = True
        params.debug.deactivate_stochastic_effects = True
    elif mode == 'spatial':
        params.film_render.grain.active = False
    else:
        raise ValueError(mode)
    params.camera.auto_exposure = mode == 'autoexp'
    params.io.input_color_space = entry.primaries
    params.io.input_cctf_decoding = False
    params.io.output_color_space = 'sRGB'
    params.io.output_cctf_encoding = True
    params.io.input_gamut_compress = spec.input_gamut_compress
    params.io.output_gamut_compress = spec.output_gamut_compress
    params = digest_params(params)
    params.io.scan_film = bool(info['positive'])
    gain = color_spaces.input_exposure_gain(spec.input_color_space, spec.stops_above_midgray)
    return params, entry, gain


def decode_input(codes, variant):
    import colour
    cs = variant_def(variant)[0]
    if cs == 'sRGB':
        return colour.cctf_decoding(codes, function='sRGB')
    if cs == 'Panasonic V-Log':
        return colour.models.log_decoding_VLog(codes)
    from spektrafilm_lut_creator import color_spaces
    return color_spaces.decode_cctf(codes, cs)  # probe variants only


def cmd_direct(film, variant, src, dst, mode):
    from spektrafilm.runtime.pipeline import SimulationPipeline
    params, entry, gain = direct_params(film, variant, mode)
    img = np.load(src)
    lin = decode_input(img, variant) * gain
    out = SimulationPipeline(params).process(lin.astype(np.float64))
    np.save(dst, np.asarray(out, np.float64))
    print(json.dumps({'film': film, 'variant': variant, 'mode': mode, 'gain': gain, 'primaries': entry.primaries,
                      'shape': list(img.shape), 'scan_film': bool(params.io.scan_film)}))


def cmd_info():
    import importlib.metadata as md
    import colour
    from spektrafilm_lut_creator import cli, color_spaces
    from spektrafilm_lut_creator.cli import _list_profiles_by_stage
    films = [film_info(f) for f in _list_profiles_by_stage('filming')]
    probe = np.linspace(0, 1, 1001)
    checks = {}
    for v in VARIANTS:
        cs = VARIANTS[v][0]
        checks[v] = {'max_abs_decode_diff_vs_exporter': float(np.max(abs(
            decode_input(probe, v) - color_spaces.decode_cctf(probe, cs)))),
            'primaries': color_spaces.get(cs).primaries,
            'gain': color_spaces.input_exposure_gain(cs, spec_for('kodak_portra_400', v)[1].stops_above_midgray),
            'stops_above_midgray': spec_for('kodak_portra_400', v)[1].stops_above_midgray}
    pk = {d.metadata['Name']: d.version for d in md.distributions()}
    print(json.dumps({'python': sys.version, 'spektrafilm': md.version('spektrafilm'), 'colour': colour.__version__,
                      'packages': dict(sorted(pk.items())), 'films': films, 'variants': checks}))


if __name__ == '__main__':
    a = sys.argv[1:]
    {'export': lambda: cmd_export(*a[1:4]), 'direct': lambda: cmd_direct(*a[1:6]), 'info': cmd_info}[a[0]]()
