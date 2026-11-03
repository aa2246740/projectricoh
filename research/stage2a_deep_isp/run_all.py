#!/usr/bin/env python3
"""Run the current two-package Stage 2a build and verification workflow."""
from pathlib import Path
import subprocess
import sys

if __name__ == '__main__':
    script = Path(__file__).resolve().with_name('build_packages.py')
    subprocess.run([sys.executable,'-I','-B',str(script)],check=True)
