#!/usr/bin/python3
"""以真实链接比较额外 resident 关闭门的成本。诊断代码不进入默认源码。"""
from pathlib import Path
import importlib.util
import json
import shutil

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('r2_measure',HERE/'measure_r2.py')
M=importlib.util.module_from_spec(spec);spec.loader.exec_module(M)
M.preflight()
source=M.TEMP/'r2-gate-source'
if source.exists():shutil.rmtree(source)
shutil.copytree(M.SOURCE,source)
p=source/'hooks.c';s=p.read_text();old='    if(hook==51){\n';assert s.count(old)==1
p.write_text(s.replace(old,old+'        if(!rv_boot_proven())return;\n'))
p=source/'resident.h';p.write_text(p.read_text()+'\nuint32_t rv_boot_proven(void);\n')
p=source/'bridges.S';p.write_text(p.read_text()+'''
.section .text.rv_boot_proven,"ax"
.balign 4
.global rv_boot_proven
rv_boot_proven:
ldi r0,#0
jmp lr
''')
baseline=json.loads((HERE/'evidence_r2/neutral/measurement.json').read_text())
M.SOURCE=source;M.HERE=HERE/'gate_cost'
result=M.build('neutral')
out=HERE/'evidence_r2/gate-cost.json'
out.write_text(json.dumps(dict(baseline_bytes=baseline['code_bytes'],
    with_resident_off_gate_bytes=result['code_bytes'],
    added_bytes=result['code_bytes']-baseline['code_bytes'],limit=16,
    diagnostic_only=True),indent=2)+'\n')
print(out.read_text())
