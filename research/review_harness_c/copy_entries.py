"""Copy write-producing runners and redirect their output roots for review."""
import difflib
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from scope_guard import HERE, ROOT, emit, enable, sha

enable()
records=[]
for source,destination in [('tools/speedlab/legacy.py','legacy.py'),
                           ('tools/speedlab/content_cache.py','content_cache.py'),
                           ('tools/speedlab/emulator.py','emulator.py'),
                           ('tools/speedlab/adapters/snapshot.py','adapters/snapshot.py')]:
    original=(ROOT/source).read_text()
    copied=original
    if destination=='legacy.py':
        copied=copied.replace('HERE = ROOT / "research/speed_hillclimb"','HERE = ROOT / "research/review_harness_c"')
        copied=copied.replace("sys.path.insert(0, str(ROOT / 'tools/speedlab'))","sys.path.insert(0, str(HERE))")
        copied=copied.replace("sys.path.remove(str(ROOT/'tools/speedlab'))","\n    while str(HERE) in sys.path:\n        sys.path.remove(str(HERE))")
        copied=copied.replace('/Volumes/Workspace/Scratch/tmp/projectricoh/speed-hillclimb',
                              '/Volumes/Workspace/Scratch/tmp/projectricoh/review-harness-c')
        copied=copied.replace(' or p.is_relative_to(ROOT / "tools/native_harness_c")','')
    if destination=='adapters/snapshot.py':
        copied=copied.replace('LOCAL = ROOT / "research/speed_hillclimb/local/snapshots"',
                              'LOCAL = ROOT / "research/review_harness_c/local/snapshots"')
        copied=copied.replace('EVIDENCE = [ROOT / "research/speed_hillclimb/local", ROOT / "tools/speedlab/local"]',
                              'EVIDENCE = [ROOT / "research/review_harness_c"]')
    if destination=='emulator.py':
        copied=copied.replace('def binding(snap, profile, card, meta):',
                              'TOOLS = Path(__file__).resolve().parent\n\ndef binding(snap, profile, card, meta):')
    target=HERE/destination
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(copied)
    diff=''.join(difflib.unified_diff(original.splitlines(True),copied.splitlines(True),fromfile=source,tofile=destination))
    (HERE/'local'/(Path(destination).stem+'-copy.diff')).write_text(diff)
    records.append(dict(source=source,target=destination,original_sha256=sha(ROOT/source),copy_sha256=sha(target),
                        adaptation='output roots and offline review common module' if diff else 'byte-identical copy'))
emit(HERE/'local/copied-runners.json',records)
print('Copied',len(records),'runners',flush=True)
