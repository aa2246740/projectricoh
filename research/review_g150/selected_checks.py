"""Run the remaining focused checks through the common Python runner."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import g150_checks as F
import review_checks as C
import independent_checks as I

if __name__ == '__main__':
    cases = {name:F.CASES[name] for name in ('held-lock-g150','race-at-s-ok')}
    cases['glyph-cleanup-contract'] = C.glyph_cleanup_contract
    I.CASES.clear(); I.CASES.update(cases); I.main()
