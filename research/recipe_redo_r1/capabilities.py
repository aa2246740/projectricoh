"""Read the explicit per-unit hardware authorization for this study."""
from pathlib import Path
import json

HERE=Path(__file__).resolve().parent


def mount_l1_enabled():
    path=HERE/'local/mount_L1_authorization.json'
    return path.exists() and json.loads(path.read_text()).get('enabled_for_fitting') is True


def main_level(unit):
    return 1 if unit!='mount-a12' or mount_l1_enabled() else 0


def mount_probe_pending(unit,level):
    return unit=='mount-a12' and level==1 and not mount_l1_enabled()
