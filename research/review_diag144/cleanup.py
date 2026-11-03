"""Remove only this review's dedicated scratch directory after input verification."""
from pathlib import Path
import shutil
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import scope
assert scope.SCRATCH == Path('/Volumes/Workspace/Scratch/tmp/projectricoh/review-diag144')
assert not scope.SCRATCH.is_symlink()
assert scope.SCRATCH.resolve() == scope.SCRATCH
print('INPUTS_UNCHANGED', scope.freeze_check())
if scope.SCRATCH.exists():
    shutil.rmtree(scope.SCRATCH)
assert not scope.SCRATCH.exists()
print('REVIEW_TMPDIR_CLEAN')
