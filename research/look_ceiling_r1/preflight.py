"""Serial preparation checks; never creates an extra parallel numerical process."""
import ast
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import runtime as rt
import check_model
import two_pass
import freeze_sources
import target_diagnostics
import relocation

def main():
    for path in rt.HERE.glob('*.py'):ast.parse(path.read_text(),filename=str(path))
    relocation.main()
    check_model.main()
    two_pass.check(True)
    freeze_sources.main()
    target_diagnostics.main()
    rt.finish('preflight')

if __name__=='__main__':main()
