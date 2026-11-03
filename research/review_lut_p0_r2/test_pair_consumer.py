from pathlib import Path
import importlib.util
import json
HERE=Path(__file__).resolve().parent
sp=importlib.util.spec_from_file_location('pair',HERE/'decode_pair.py')
p=importlib.util.module_from_spec(sp);sp.loader.exec_module(p)
cases=[]
for gen in (113,114):
    base=HERE/'edges'/str(gen)
    # A good earlier run followed by an interrupted run must fail as a pair.
    try:p.newest([base/'interrupted-newest-slot0.BIN',base/'interrupted-newest-slot1.BIN'],8,10000)
    except ValueError as e:cases.append(dict(generation=gen,invalid_newest_rejected=str(e)))
    else:raise AssertionError('older DONE selected')
    valid=p.newest([HERE/'trace'/str(gen)/'first-publish-retry.BIN'],10,10000)
    assert valid['complete'] and valid['tick_hz']==1000
    try:p.newest([HERE/'trace'/str(gen)/'first-publish-retry.BIN'],10,10001)
    except ValueError:pass
    else:raise AssertionError('screen mismatch accepted')
(HERE/'pair-consumer-results.json').write_text(json.dumps(dict(status='PASS',cases=cases,screen_mismatch_rejected=True),indent=2)+'\n')
print('PASS pair consumer rejects newest invalid instead of choosing older DONE; screen REF DT checked')
