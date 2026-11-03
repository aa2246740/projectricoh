"""Use the retained final-image runners with the review write fence."""
from pathlib import Path
import ast
import importlib.util
import sys
import types

sys.path.insert(0, str(Path(__file__).resolve().parent))
from review_scope import ROOT, SOURCE, OUT, load, save, sha, file_sha

common = types.ModuleType('common')
common.ROOT, common.OUT = ROOT, SOURCE
common.load, common.save, common.sha, common.file_sha = load, save, sha, file_sha
sys.modules['common'] = common
sys.path.insert(0, str(SOURCE))

path = SOURCE / 'differential.py'
tree = ast.parse(path.read_text(), filename=str(path))
copy_steps = [node for node in tree.body if isinstance(node, ast.For)
              and isinstance(node.target, ast.Tuple)
              and [part.id for part in node.target.elts] == ['g', 'tree']]
assert len(copy_steps) == 1
tree.body.remove(copy_steps[0])
differential = types.ModuleType('differential')
differential.__file__ = str(path)
sys.modules['differential'] = differential
exec(compile(tree, str(path), 'exec'), differential.__dict__)


class RuntimeFiles:
    def __truediv__(self, name):
        if name.startswith('container'):
            generation = int(name[9:12])
            suffix = 'b' if generation == 120 else ''
            return ROOT / f'firmware/package_v36_g{generation}{suffix}/SD_ROOT/GXRCE.DAT'
        return SOURCE / name


differential.ex.OUT = RuntimeFiles()
differential.ex.pb.CACHE = OUT / 'decode'
differential.IMAGE = (ROOT/'firmware/package_v36_g120b/SD_ROOT/GXRCE.DAT').read_bytes()
differential.EXPAND = load(SOURCE/'artifacts.py','review_runtime_expand').expand(differential.IMAGE)
save('runtime-binding.json', dict(dat120_sha256=sha(differential.IMAGE),
     omitted_source_step='The source helper copies snapshots into its own directory at import time. That step is omitted; the runner reads each existing package directly.',
     instruction_decoder='Retained decode rows checked against the final ELF by machine.py',
     output_directory=str(OUT)))


def runner(generation):
    return differential.ex.Runner(generation)
