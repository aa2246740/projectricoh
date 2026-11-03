"""Observe the original r3 subclass signature before using its documented adaptation."""
import contextlib
import hashlib
import json
from pathlib import Path
import sys
import traceback

sys.path.insert(0, str(Path(__file__).resolve().parent))
from replay import environment

fixture, output = environment('r3-original-interface')
prior = Path(__file__).resolve().parent.parent/'review_studio_gpu_preview_r3/extra_boundaries.py'
namespace = {'__file__': str(prior), '__name__': '__main__'}
error = None
with (output/'stdout.log').open('w') as stdout, (output/'stderr.log').open('w') as stderr, contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
    try:
        exec(compile(prior.read_text(), str(prior), 'exec'), namespace)
    except TypeError as exc:
        error = str(exc)
        traceback.print_exc()
assert error and 'root' in error and 'unexpected keyword' in error
result = {'original': str(prior), 'sha256': hashlib.sha256(prior.read_bytes()).hexdigest(),
          'observed_exception': error, 'meaning': 'Original subclass does not accept the current root keyword; use the preserved trigger with forwarded keywords for the behavior check.'}
(output/'legacy-interface.json').write_text(json.dumps(result, indent=2)+'\n')
print(json.dumps(result))
