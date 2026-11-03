"""Conservative change-log matching model; no camera file operations.

Only closed file-number intervals within one declared boot/media epoch are
assigned. Missing session anchors, clock ties, gaps and open tails stay unknown.
The model assumes reliable boot/sequence production, which current DATs lack.
"""
import json
from pathlib import Path
import sys
import zlib
sys.path.insert(0,str(Path(__file__).resolve().parent))
import common as c
c.guard(600)


def encode(event):
    body=json.dumps(event,sort_keys=True,separators=(',',':')).encode()
    return body+b'\t'+f'{zlib.crc32(body):08X}'.encode()+b'\n'


def decode(raw):
    events=[];invalid=[]
    for index,line in enumerate(raw.splitlines(keepends=True)):
        try:
            if not line.endswith(b'\n'):raise ValueError('Incomplete line')
            body,checksum=line[:-1].rsplit(b'\t',1)
            if len(checksum)!=8 or int(checksum,16)!=zlib.crc32(body):raise ValueError('CRC')
            event=json.loads(body)
            if set(event)!={'epoch','seq','next_file','time','kind','recipe','complete'}:raise ValueError('Fields')
            if type(event['seq'])!=int or event['seq']<0 or type(event['next_file'])!=int:raise ValueError('Range')
            events.append(event)
        except (ValueError,KeyError,TypeError):invalid.append(index)
    return events,invalid


def match(file_number,events,invalid,epoch=None):
    # Epoch is external evidence, not something recoverable from a JPEG's date.
    if invalid or epoch is None:return None
    ev=[e for e in events if e['epoch']==epoch]
    if not ev or ev[0]['kind']!='boot' or ev[0]['seq']!=0:return None
    for a,b in zip(ev,ev[1:]):
        if b['seq']!=a['seq']+1 or b['next_file']<a['next_file']:return None
        if a['next_file']<=file_number<b['next_file']:
            return a['recipe'] if a['complete'] and a['kind'] in ('boot','applied','adj_closed') else None
    return None


def event(seq,num,recipe,kind='applied',epoch='boot-7',complete=True,time='2000:01:01 00:00:00'):
    return dict(epoch=epoch,seq=seq,next_file=num,time=time,kind=kind,recipe=recipe,complete=complete)


def main():
    base=[event(0,100,'04','boot'),event(1,103,'01'),event(2,106,'02')]
    raw=b''.join(map(encode,base));checks=[]
    def check(name,number,raw,epoch,expected):
        events,bad=decode(raw);actual=match(number,events,bad,epoch)
        assert actual==expected,(name,actual,expected)
        checks.append(dict(name=name,expected=expected,actual=actual,invalid_lines=bad))
    check('camera-year-2000',101,raw,'boot-7','04')
    check('same-second-file-boundary',104,raw,'boot-7','01')
    check('open-tail-card-full-or-battery-loss',107,raw,'boot-7',None)
    check('journal-deleted',104,b'','boot-7',None)
    check('journal-crc-damaged',104,raw.replace(b'"01"',b'"08"'),'boot-7',None)
    check('journal-last-line-torn',104,raw[:-4],'boot-7',None)
    check('missing-boot-before-first-adj',104,b''.join(map(encode,base[1:])),'boot-7',None)
    check('no-epoch-evidence-in-old-jpeg',104,raw,None,None)
    gap=[base[0],event(3,106,'02')]
    check('lost-recipe-change-after-card-full',104,b''.join(map(encode,gap)),'boot-7',None)
    check('my-native-settings-unknown',101,b''.join(map(encode,[event(0,100,None,'boot',complete=False),base[1]])),'boot-7',None)
    check('card-removal-new-epoch',104,raw,'boot-8',None)
    rollback=[base[0],event(1,90,'01')]
    check('file-counter-reset',95,b''.join(map(encode,rollback)),'boot-7',None)
    unsafe=base[-1]['recipe']
    assert unsafe=='02' # A naive forward fill wrongly labels the next pure-04 boot.
    c.dump('log_matching_results.json',dict(status='PASS',checks=checks,
           naive_unlogged_reboot=dict(previous_recipe=unsafe,actual_normal_boot_recipe='04',false_label=unsafe),
           limitation='This matcher needs epoch/file-range anchors absent from existing photo EXIF and DAT-only change logs'))
    c.finish('log-matching')
    print('PASS',len(checks))


if __name__=='__main__':main()
