"""Block until <dir>/DONE exists or the timeout passes, using kqueue directory events (no polling).

Usage: /usr/bin/python3 -I -B research/unit28_stock/wait_done.py <dir> <seconds>
Prints the DONE content, or WAITING if the timeout passed first."""
import os
import select
import sys
import time
from pathlib import Path

folder, limit = Path(sys.argv[1]), float(sys.argv[2])
end = time.monotonic() + limit
fd = os.open(folder, os.O_RDONLY)
kq = select.kqueue()
event = select.kevent(fd, filter=select.KQ_FILTER_VNODE, flags=select.KQ_EV_ADD | select.KQ_EV_CLEAR,
                      fflags=select.KQ_NOTE_WRITE)
while not (folder / 'DONE').exists():
    left = end - time.monotonic()
    if left <= 0:
        print('WAITING')
        sys.exit(0)
    kq.control([event], 1, left)
print('DONE', (folder / 'DONE').read_text().strip())
