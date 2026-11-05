"""Call the original g156 instruction gate; rebind outputs, never product inputs."""
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0,str(ROOT/'research/g156'))
import common as C

C.HERE = HERE/'parent-generation'
C.LOCAL = C.HERE/'local'
C.TMP = C.LOCAL/'tmp'
C.ALLOWED = (HERE,)
(C.HERE/'evidence').mkdir(parents=True,exist_ok=True)

import r2_generation_harness

sys.argv = ['r2_generation_harness.py','--backend','python','--label','independent-native-generations']
r2_generation_harness.main()
