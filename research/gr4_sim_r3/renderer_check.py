"""Exercise the actual scene-array CLI and read its output archive."""
from pathlib import Path
import subprocess
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import runtime as rt
from runtime import np


def main():
    values = np.repeat(np.array([0., .018, .18, .9])[:, None], 3, axis=1)
    fixture = rt.LOCAL / 'render_input.npy'
    np.save(fixture, values)
    command = [sys.executable, '-I', '-B', str(rt.HERE / 'render.py'), str(fixture), '--output', 'render_smoke.npz']
    gate = rt.read(rt.LOCAL / 'gate.json')
    ordinary = subprocess.run(command, cwd=rt.ROOT, capture_output=True, text=True)
    if not gate['accepted']: assert ordinary.returncode != 0
    research = subprocess.run(command + ['--diagnostic'], cwd=rt.ROOT, capture_output=True, text=True)
    assert research.returncode == 0, research.stderr
    output = rt.arrays(rt.LOCAL / 'render_smoke.npz')
    assert set(output) == {'standard', 'positive', 'negative'}
    for row in output.values():
        assert row.shape == (4, 3) and np.isfinite(row).all()
        assert row.min() >= 0 and row.max() <= 1 and row[2].mean() > 0
    assert np.max(abs(output['positive'] - output['negative'])) > .01
    info = rt.read(rt.LOCAL / 'render_smoke.npz.json')
    assert info['diagnostic_only'] == (not gate['accepted'])
    rt.dump('renderer_verification.json', dict(status='PASS', evidence='电脑预测',
        ordinary_exit=ordinary.returncode, research_exit=research.returncode,
        input_shape=values.shape, output_modes=sorted(output),
        accepted_target=gate['accepted'], actual_archive_read=True))
    print('Scene-array CLI and actual output archive checked.', flush=True)


if __name__ == '__main__': main()
