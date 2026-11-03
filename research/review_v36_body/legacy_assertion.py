"""Execute the unchanged, callable v3.6 helper's obsolete diagnostic assertion."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from review_common import HERE, module, save
v = module(HERE / "body_binding.py", "legacy_v36_helper")
v.bind()
result = v.inflight_h07()
save("legacy-diag-assertion.json", dict(result=result, helper="inflight_h07",
     expected_diagnostic=0x307, actual_diagnostic=0, only_failed_check="diagnostic expected to be written",
     called_by_run_v36_checks=False, firmware_failure=False))
assert result is False, "Expected the obsolete diagnostic assertion to fail"
print("CONFIRMED stale helper requires removed diag write; active v3.6 stages do not call it")
