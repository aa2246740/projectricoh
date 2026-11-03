from pathlib import Path
import os,sys
ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
os.chdir(ROOT)
os.environ['TMPDIR']=str(HERE/'local/tmp')
os.environ['PYTHONDONTWRITEBYTECODE']='1'
os.environ['GIT_OPTIONAL_LOCKS']='0'
os.environ['CLANG_MODULE_CACHE_PATH']=str(HERE/'local/tmp/modules')
os.execv('/usr/bin/sandbox-exec',['sandbox-exec','-f',str(HERE/'fence.sb'),'/usr/bin/python3','-I','-B',*sys.argv[1:]])
