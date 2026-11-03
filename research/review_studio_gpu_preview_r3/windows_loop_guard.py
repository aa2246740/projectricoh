"""Reproduce the network guard conflict using CPython's Windows socketpair path."""
import asyncio
import inspect
import json
import os
from pathlib import Path
import socket
import sys
from unittest.mock import patch

SOURCE = Path(os.environ['REVIEW_SOURCE'])
sys.path.insert(0, str(SOURCE / 'src'))
from gxr_studio import audit

before = list(audit.network_attempts())
audit.forbid_network(True)
error = None
try:
    with patch.object(socket, 'socketpair', socket._fallback_socketpair):
        loop = asyncio.new_event_loop()
        loop.close()
except PermissionError as exc:
    error = type(exc).__name__ + ':' + str(exc)
finally:
    audit.forbid_network(False)
after = audit.network_attempts()
result = {'scope':'Host reproduction of the Windows-selected CPython socketpair path, not a Windows run',
          'event_loop_initialization_error':error,'network_attempts_before':before,'network_attempts_after':after,
          'fallback_source':inspect.getsourcefile(socket._fallback_socketpair)}
assert error and len(after) == len(before) + 1 and '127.0.0.1' in after[-1]
out = Path(os.environ.get('REVIEW_OUT', Path(__file__).resolve().parent))
(out / 'windows-loop-guard.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result))
