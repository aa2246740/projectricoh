"""A local blocking fixture for controller lifetime checks; no camera model."""
from pathlib import Path
import argparse,json,os,select,sys,time
def main():
    p=argparse.ArgumentParser();p.add_argument('--ready');p.add_argument('--hold',action='store_true');p.add_argument('--output',required=True);a=p.parse_args()
    fd=int(os.environ['G152_CONTROLLER_LEASE_FD']);os.fstat(fd)
    if a.ready:
        with open(a.ready,'w') as stream:stream.write(json.dumps(dict(pid=os.getpid(),lease_fd=fd))+'\n')
    if a.hold:
        assert select.select([sys.stdin],[],[],60)[0]
        assert sys.stdin.readline().strip()=='done'
    Path(a.output).write_text(json.dumps(dict(status='PASS',pid=os.getpid(),lease_fd_open=True,ended_ns=time.time_ns()))+'\n')
if __name__=='__main__':main()
