"""Menu and Splt checks in the ownership session: restore the H01 eight-row parent first, then run the product checks."""
from pathlib import Path
import runpy
HERE = Path(__file__).resolve().parent

def run(context, arguments, out, sessions):
    unit = arguments[arguments.index('--unit') + 1]
    capture = runpy.run_path(str(HERE / 'capture_state.py'))
    products = [item for session in sessions for item in (session if isinstance(session, tuple) else (session,))
                if hasattr(item, 'image_base') and hasattr(item, 'rpc')]
    product = next(item for item in products if item.image_base)
    capture['h01_restore'](product, unit, out)
    runpy.run_path(str(HERE / 'product_checks.py'))['run'](context, arguments, out, sessions)
