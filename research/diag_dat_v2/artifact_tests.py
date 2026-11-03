"""Exercise the packaged DAT through the existing native instruction model."""
from pathlib import Path
import json
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parent))
import legacy_call as legacy
import scope

def main():
    sys.addaudithook(legacy.fence)
    support=legacy.load_path(scope.ROOT/'research/diag_dat_v1/native_support.py')
    evidence=[]
    for unit in ('50mm','28mm','mount'):
        value=support['setup'](unit)
        h,p=value[:2]
        support['open_menu'](h,p)
        pages=[]
        for expected in 'ABCDFHA':
            rows=support['text_rows'](h,p)
            assert len(rows)==8 and all(0<len(s)<=8 for s in rows),(unit,'row-shape')
            assert rows[0][0]==expected,(unit,'page-order',rows)
            pages.append(rows)
            if expected=='H':
                assert rows[7]=='OK',(unit,'heap-status',rows)
                assert rows[4].startswith('M1') and rows[5]=='SI0007B0',(unit,'own-blocks',rows)
            support['action'](h,p,'disp')
        assert len({rows[0][1:] for rows in pages})==1,(unit,'same-open-sequence')
        scope.save(scope.HERE/'artifact-'+unit+'.json',dict(status='PASS',unit=unit,pages=pages,
            dat_sha256=scope.sha(scope.ROOT/'firmware/package_v36_diag2/local/SD_ROOT/GXRCE.DAT')))
        evidence.append(dict(unit=unit,pages=len(pages)))
        print('ARTIFACT',unit,'RETURN',0,'COUNT',len(pages),flush=True)
    scope.save(scope.HERE/'artifact-tests.json',dict(status='PASS',units=evidence))

if __name__=='__main__':
    try:main()
    except Exception as e:
        print('ARTIFACT RETURN 1 TYPE',type(e).__name__)
        if isinstance(e,AssertionError):
            print('ACTUAL',str(e)[:700])
        else:print('DETAIL',str(e)[:500])
        tb=e.__traceback__;frames=[]
        while tb:
            frames.append((Path(tb.tb_frame.f_code.co_filename).name,tb.tb_frame.f_code.co_name,tb.tb_lineno));tb=tb.tb_next
        print('FRAMES',json.dumps(frames))
        raise SystemExit(1)
