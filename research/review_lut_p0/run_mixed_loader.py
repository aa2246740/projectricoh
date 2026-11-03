from pathlib import Path
import importlib.util
import json

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('review_runner',HERE/'run_review.py')
r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)
r.freeze()
commands=[json.loads(line) for line in (r.OUT/'commands.jsonl').read_text().splitlines()]
compile_command=next(x['argv'] for x in commands if x['label']=='host-compile-0')
compile_command[compile_command.index('-c')+1]=str(HERE/'mixed_loader.c')
compile_command[compile_command.index('-o')+1]=str(HERE/'mixed_loader.o')
r.run(compile_command,'mixed-loader-compile')
link_command=next(x['argv'] for x in commands if x['label']=='host-link')
link_command=[str(HERE/'mixed_loader.o') if x.endswith('/0-host_checks.o') else x for x in link_command]
link_command[link_command.index('-o')+1]=str(HERE/'mixed_loader')
r.run(link_command,'mixed-loader-link')
result=r.run([HERE/'mixed_loader',r.OUT/'GXRCE.DAT',r.c.FULL,r.c.FULL114],'mixed-loader-run')
print(result.stdout,end='')
r.freeze()
