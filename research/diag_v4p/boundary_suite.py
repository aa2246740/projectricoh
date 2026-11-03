"""One foreground worker for the three units' focused repair boundaries."""
from pathlib import Path
import sys,time
sys.path.insert(0,str(Path(__file__).resolve().parent))
import scope as s
import host as H
import readonly_paths as ro
import cross_body as cross
import boundaries as b
import quick_model

def main():
    s.enable();started=time.monotonic()
    units=('28mm','mount') if '--resume-28mm' in sys.argv else ('50mm','28mm','mount')
    for unit in units:
        if unit!='50mm':quick_model.run(unit)
        ro.run(unit);cross.run(unit)
        for name,fn in (('cursors',b.cursor_cases),):
            result=fn(unit)
            s.save(s.HERE/'evidence'/('boundary-'+name+'-'+unit+'.json'),dict(status='PASS',unit=unit,dat_sha256=s.sha(H.DAT),result=result))
            print('PASS',name,unit,flush=True)
    s.save(s.HERE/'evidence/boundary-suite.json',dict(status='PASS',dat_sha256=s.sha(H.DAT),seconds=round(time.monotonic()-started,2)))
    print('PASS focused boundaries',flush=True)
if __name__=='__main__':main()
