"""Run the shipped DAT with init persisted and all later lock tries busy."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import scope
scope.enable_fence()
import accept_diag146 as a

a.HERE = scope.HERE / 'counterexample'
a.HERE.mkdir(exist_ok=True)
original_init = a.Card.__init__
def init(card, content, faults):
    original_init(card, content, dict(faults, busy={2, 3, 4}))
a.Card.__init__ = init
sys.argv = [__file__, 'allwritefail']
a.main()
data = bytes(a.LAST['card'].content)
(a.HERE / 'GXRTRACE.BIN').write_bytes(data)
reference = scope.HERE / 'host-files/accept146-28mm-retire-last.bin'
result = dict(equal_to_retired=data == reference.read_bytes(),
              retired_sha256=scope.sha(reference),
              menus_then_busy_sha256=scope.sha(a.HERE / 'GXRTRACE.BIN'),
              menus_executed=3, init_writes=1,
              later_busy_tries=3, full_file_bytes=len(data),
              boundary='Final DAT/resident instructions; card and lock contention are injected.')
scope.save(a.HERE / 'comparison.json', result)
assert result['equal_to_retired'],result
print('COUNTEREXAMPLE_DONE',result,flush=True)
