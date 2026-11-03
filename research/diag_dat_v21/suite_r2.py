from pathlib import Path
import runpy,sys
here=Path(__file__).resolve().parent
sys.argv=[str(here/'call.py'),'research/diag_dat_v2/suite_r2.py',*sys.argv[1:]]
runpy.run_path(str(here/'call.py'),run_name='__main__')
