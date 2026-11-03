"""Compile current C field offsets without staging or changing the package."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from build_package import layout
layout()
print('PASS current C layouts rebuilt in review output')
