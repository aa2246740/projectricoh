from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from scope import ROOT, WORK, LOCAL, setup, frozen

ENGINE = ROOT / 'firmware/engine_v54_g137'
PACKAGE = ROOT / 'firmware/package_v38_g137/SD_ROOT'

def enable():
    setup()

def check_inputs():
    import json
    before = json.loads((WORK / 'inputs-before.json').read_text())
    assert before == frozen(), 'Protected files changed'
