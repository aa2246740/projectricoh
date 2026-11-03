"""Replace this process with the compiler under the same wall timer."""
from pathlib import Path
import os
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import review_common as c

c.start()
compiler = '/usr/bin/clang'
args = [compiler, '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror', '-dynamiclib',
        '-fsanitize=undefined', '-fsanitize-trap=undefined', '-fno-sanitize-recover=all',
        str(c.HERE / 'heap_reader.c'), '-o', str(c.LOCAL / 'heap_reader.dylib')]
os.execv(compiler, args)
