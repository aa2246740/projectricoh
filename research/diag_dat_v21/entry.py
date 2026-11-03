from pathlib import Path
import linecache,runpy,sys
linecache.getline=lambda *args,**kwargs:''
linecache.getlines=lambda *args,**kwargs:[]
sys.path.insert(0,str(Path(__file__).resolve().parent))
path=sys.argv[1];sys.argv=sys.argv[1:]
try:runpy.run_path(path,run_name='__main__')
except SystemExit:raise
except BaseException as e:
    frames=[];tb=e.__traceback__
    while tb:
        frames.append((Path(tb.tb_frame.f_code.co_filename).name,tb.tb_frame.f_code.co_name,tb.tb_lineno))
        tb=tb.tb_next
    print('ERROR',type(e).__name__,'FRAMES',frames,flush=True)
    raise SystemExit(1)
