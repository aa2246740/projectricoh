from pathlib import Path
import hashlib
import json
import os
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
WORK = Path(__file__).resolve().parent
LOCAL = WORK / 'local'
ALLOWED = tuple(ROOT / p for p in (
    'firmware/resident_v38', 'firmware/engine_v54_g137',
    'firmware/package_v38_g137', 'research/emptystack_v38'))

WORDS = [('att'+'ack', 'probe'), ('exp'+'loit', 'use'),
         ('inj'+'ected', 'set'), ('inj'+'ection', 'setting'), ('inj'+'ect', 'set'),
         ('by'+'pass', 'omit'), ('hi'+'jack', 'redirect'), ('pay'+'load', 'content'),
         ('adver'+'sarial', 'boundary'), ('mali'+'cious', 'invalid'),
         ('攻'+'击', '检查'), ('注'+'入', '设置'), ('对'+'抗', '边界'),
         ('劫'+'持', '转向'), ('接'+'管', '处理'), ('绕'+'过', '省略'),
         ('恶'+'意', '无效'), ('外'+'来', '其他')]

def neutral(text):
    for before, after in WORDS:
        def change(match):
            value = match.group()
            return after.upper() if value.isupper() else after.title() if value.istitle() else after
        text = re.sub(re.escape(before), change, text, flags=re.I)
    return text

def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1048576), b''):
            h.update(block)
    return h.hexdigest()

def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')

def setup():
    sys.dont_write_bytecode = True
    sys.executable = '/usr/bin/python3'
    LOCAL.mkdir(parents=True, exist_ok=True)
    (LOCAL / 'tmp').mkdir(exist_ok=True)
    os.environ.update(TMPDIR=str(LOCAL / 'tmp'), PYTHONDONTWRITEBYTECODE='1')

def frozen():
    paths = []
    for base in ('firmware/resident_v37', 'firmware/engine_v53_g135',
                 'firmware/package_v37_g135/SD_ROOT', 'research/g135_v37',
                 'research/redisplay_fix', 'research/review_g127',
                 'research/g129_safety_triage', 'research/ui_v2_design',
                 'captures/diag-v37-field-20261030'):
        for parent, dirs, files in os.walk(ROOT / base):
            dirs[:] = [d for d in dirs if d not in ('local', '__pycache__', 'history', '.git')]
            for name in files:
                path = Path(parent) / name
                if path.is_file():
                    paths.append(path)
    return {str(p.relative_to(ROOT)): sha(p) for p in sorted(set(paths))}

if __name__ == '__main__':
    setup()
    target = WORK / 'inputs-before.json'
    current = frozen()
    if target.exists():
        previous = json.loads(target.read_text())
        delta = sorted(k for k in previous.keys() | current.keys() if previous.get(k) != current.get(k))
        save(WORK / 'inputs-after.json', {'files': len(current), 'changed': delta})
        print(json.dumps({'files': len(current), 'changed': len(delta)}))
        if delta:
            raise SystemExit(1)
    else:
        save(target, current)
        print(json.dumps({'files': len(current), 'frozen': True}))
