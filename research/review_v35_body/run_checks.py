"""Run existing checks read-only; redirect all their output into this review."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from review_common import HERE, ROOT, module
which=sys.argv[1]
if which=="conformance":
    module(ROOT/"tools/native_harness/conformance.py","review_conformance").main()
elif which=="inherited":
    import guard
    guard.HERE=HERE
    s=module(ROOT/"tools/native_harness/scenarios.py","review_inherited")
    sys.argv=[str(ROOT/"tools/native_harness/scenarios.py"),"--out",str(HERE/"inherited.json")]
    raise SystemExit(s.main())
elif which=="v35":
    module(ROOT/"firmware/image_v35/harness_scenarios/run_v35.py","review_v35_checks").main()
else:
    raise SystemExit("unknown check")
