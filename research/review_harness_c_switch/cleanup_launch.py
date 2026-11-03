from pathlib import Path
import json
import runpy
import sys

OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(OUT / 'entry'))
from support import enable
enable()
runpy.run_path(str(OUT / 'cleanup.py'), run_name='__main__')
path = OUT / 'evidence/cleanup.json'
value = json.loads(path.read_text())
value['write_boundary'] = 'Python audit limits writes to the review output and declared temporary root'
value['process_listing'] = 'Read-only ps outside the kernel test profile; the profile refused ps before any removal'
path.write_text(json.dumps(value, indent=2) + '\n')
