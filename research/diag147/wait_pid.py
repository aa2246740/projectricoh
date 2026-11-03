"""Block until a process exits (kqueue NOTE_EXIT, no polling). Usage: wait_pid.py TIMEOUT_SECONDS PID"""
import select
import sys

timeout, pid = float(sys.argv[1]), int(sys.argv[2])
kq = select.kqueue()
try:
    kq.control([select.kevent(pid, select.KQ_FILTER_PROC, select.KQ_EV_ADD, select.KQ_NOTE_EXIT)], 0)
except ProcessLookupError:
    print('gone')
    sys.exit(0)
events = kq.control(None, 1, timeout)
print('exited' if events else 'timeout')
