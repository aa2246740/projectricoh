"""Check menus in the same target session after successful ownership recovery."""
from pathlib import Path
import runpy
HERE=Path(__file__).resolve().parent

def run(context,arguments,out,sessions):
    reopen=runpy.run_path(str(HERE/'session_check.py'))
    reopen['run'](context,arguments,out,sessions)
    product=runpy.run_path(str(HERE/'product_checks.py'))
    product['run'](context,arguments,out,sessions)
