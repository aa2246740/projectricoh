"""Build additional boundary tests against the independently rebuilt real C."""
from pathlib import Path
import importlib.util
import json

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('review_runner',HERE/'run_review.py')
r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)
r.freeze()
commands=[json.loads(line) for line in (r.OUT/'commands.jsonl').read_text().splitlines()]
compile_command=next(x['argv'] for x in commands if x['label']=='host-compile-0')
compile_command[compile_command.index('-c')+1]=str(HERE/'adversarial.c')
compile_command[compile_command.index('-o')+1]=str(HERE/'adversarial.o')
r.run(compile_command,'adversarial-compile')
link_command=next(x['argv'] for x in commands if x['label']=='host-link')
link_command=[str(HERE/'adversarial.o') if x.endswith('/0-host_checks.o') else x for x in link_command]
link_command[link_command.index('-o')+1]=str(HERE/'adversarial')
r.run(link_command,'adversarial-link')
result=r.run([HERE/'adversarial',r.OUT/'GXRCE.DAT',r.c.FULL114,
              HERE/'reference-reopen.BIN',HERE/'first-publish-retry.BIN'],'adversarial-run')
print(result.stdout,end='')
d=r.plain_load(r.SOURCE/'decode.py','independent_decoder_checks')
counterexamples=[]
for name,delta,hz in [('reference-reopen',70000,7000),('first-publish-retry',110000,11000)]:
    decoded=d.decode((HERE/(name+'.BIN')).read_bytes(),10)
    assert decoded['complete'] and decoded['error']==0 and decoded['reference_delta']==delta and decoded['tick_hz']==hz
    r.save(HERE/(name+'.json'),dict(synthetic_host_ticks=True,visible_interval_ticks=10000,**decoded))
    counterexamples.append(dict(case=name,complete=True,error=0,user_seconds=10,
                                actual_tick_hz=1000,reported_tick_hz=hz,factor=hz/1000))
r.save(HERE/'adversarial-results.json',dict(status='REPRODUCED',counterexamples=counterexamples,
    native_descriptor_changed_by_H01=True,reopen_1000_extra_allocation_bytes=0,model='real C with host native boundaries'))
print('PASS counterexamples: complete/error=0 logs decode to 7x and 11x tick_hz')
r.freeze()
