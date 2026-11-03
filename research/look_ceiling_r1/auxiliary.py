"""Sequential auxiliary work in one low-priority process; no extra workers."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import metadata_controls
metadata_controls.main()
import display_oracle
display_oracle.main()
import legacy_checks
legacy_checks.main()
import two_pass
sys.argv=['two_pass.py','--indices','0:27','--nfev','80']
two_pass.main()
