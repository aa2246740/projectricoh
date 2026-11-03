"""One waiting parent and one foreground CLI child, with real OS exit status."""
import contextlib
import io
import json
import os
import signal
import sys
from pathlib import Path

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'r3'))
import diag_gate as gate


def arguments(index):
    stem=index['stem'];p=HERE/'positive'
    return ['-','--profile',str(p/(stem+'-profile.json')),'--profile-sha256',index['profile_sha256'],
            '--capture',str(p/(stem+'-capture.json')),'--capture-sha256',index['capture_sha256']]


def warm(index):
    p=HERE/'positive';stem=index['stem']
    profile=gate.profile_text((p/(stem+'-profile.json')).read_text(),index['profile_sha256'])
    capture=gate.capture_text((p/(stem+'-capture.json')).read_text(),index['capture_sha256'])
    return profile,capture


def call(argv,content):
    assert os.getpriority(os.PRIO_PROCESS,0)>=10
    reader,writer=os.pipe()
    prior_mask=signal.pthread_sigmask(signal.SIG_BLOCK,{signal.SIGINT})
    pid=os.fork()
    if pid==0:
        signal.signal(signal.SIGINT,signal.SIG_IGN)
        signal.pthread_sigmask(signal.SIG_SETMASK,prior_mask)
        os.close(reader)
        output=io.StringIO();error=io.StringIO();sys.stdin=io.StringIO(content)
        code=1
        try:
            with contextlib.redirect_stdout(output),contextlib.redirect_stderr(error):
                code=gate.main(argv)
        except BaseException as exception:
            error.write(type(exception).__name__+': '+str(exception));code=1
        result=json.dumps(dict(stdout=output.getvalue(),stderr=error.getvalue())).encode()
        with os.fdopen(writer,'wb') as stream:stream.write(result)
        os._exit(code)
    os.close(writer)
    try:
        signal.pthread_sigmask(signal.SIG_SETMASK,prior_mask)
        with os.fdopen(reader,'rb') as stream:result=json.loads(stream.read())
    finally:
        _,status=os.waitpid(pid,0)
    assert os.WIFEXITED(status),status
    return os.WEXITSTATUS(status),result
