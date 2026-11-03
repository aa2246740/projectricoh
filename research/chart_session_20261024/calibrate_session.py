"""Future calibration entrypoint: unchanged module_adapt CLI, outputs confined here.

No calibration is run as part of this session's measurement workflow.
"""
import json
from pathlib import Path
import sys
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import session_runtime as session


def main():
    session.guard()
    sys.addaudithook(session.audit)
    sys.path.insert(0, str(session.ROOT / 'research/module_adapt'))
    import support
    import calibrate
    # Preserve all model, fitting, and acceptance rules; relocate output I/O only.
    support.HERE, support.LOCAL = session.HERE, session.LOCAL
    if '--frames' in sys.argv and '--unit' in sys.argv:
        path = Path(sys.argv[sys.argv.index('--frames') + 1])
        path = path if path.is_absolute() else session.ROOT / path
        unit = sys.argv[sys.argv.index('--unit') + 1]
        frames = json.loads(path.read_text())['frames']
        if unit == 'mount':
            missing = []
            for key, f in frames.items():
                if f['module'] != unit:
                    continue
                if not isinstance(f.get('aperture_f'), (float, int)) or f['aperture_f'] <= 0:
                    missing.append(key + ': actual aperture')
                if not f.get('lens_id'):
                    missing.append(key + ': stable physical lens ID')
                if any(v in (None, 'unknown') for v in f.get('corrections', {}).values()):
                    missing.append(key + ': shading/distortion correction settings')
            if missing:
                raise SystemExit('Mount metadata incomplete; no fit started. Confirm actual ring aperture, lens ID, and correction settings: ' + '; '.join(missing[:3]))
    calibrate.main()


if __name__ == '__main__':
    main()
