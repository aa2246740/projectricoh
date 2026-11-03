#!/usr/bin/env python3
"""Verify the current Stage 2a package delivery without rebuilding."""
from pathlib import Path
import subprocess
import sys

if __name__ == '__main__':
    script = Path(__file__).resolve().with_name('verify_packages.py')
    subprocess.run([sys.executable,'-I','-B',str(script)],check=True)
