"""Reproduce duplicate-name counterexample using the actual field snapshots.

This is a filesystem boundary model, not execution of the native FAT driver.
"""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import artifacts as a
import boundary as b
import importlib.util
import struct
import zlib

def decoder():
    path=b.add(a.ENGINE/'decode_blackbox.py')
    spec=importlib.util.spec_from_file_location('model_decoder',path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    return m

def main():
    d=decoder();old0=a.read(a.CARD/'GXRBX0_entry1.BIN');old1=a.read(a.CARD/'root/GXRBX1.BIN')
    snapshots=[a.read(a.CARD/f'GXRBX0_entry{i}.BIN') for i in (3,2)]
    outcomes={}
    for method in ('create_appends_directory_entry','open_existing_overwrites_same_entry'):
        slots=[[old0],[old1]];rows=[]
        for snapshot in snapshots:
            generation=[d.read_log(s[0])['header']['flush_generation'] for s in slots]
            target=0 if generation[0]<=generation[1] else 1
            gen=max(generation)+1;p=bytearray(snapshot);struct.pack_into('>I',p,16,gen)
            struct.pack_into('>I',p,124,zlib.crc32(p[:124]));p=bytes(p)
            if method.startswith('create_'):slots[target].append(p)
            else:slots[target][0]=p
            verified=slots[target][0]==p
            rows.append(dict(input_visible_generation=generation,target=target,emitted_generation=gen,
                directory_entries=[len(x) for x in slots],verify_path_matches_written_entry=verified,
                writer_event_head=d.read_log(p)['header']['event_head']))
        outcomes[method]=rows
    assert [r['emitted_generation'] for r in outcomes['create_appends_directory_entry']]==[3,3]
    assert all(not r['verify_path_matches_written_entry'] for r in outcomes['create_appends_directory_entry'])
    assert [r['emitted_generation'] for r in outcomes['open_existing_overwrites_same_entry']]==[3,4]
    assert all(r['verify_path_matches_written_entry'] for r in outcomes['open_existing_overwrites_same_entry'])
    b.dump('blackbox_counterexample.json',dict(evidence='actual old slots and gen115 seq199/335 snapshots',
        scope='boundary model; native create semantics independently established from official bytes and user FAT directory evidence',results=outcomes))
    print('PASS duplicate-create reproduces targets [0,0], generations [3,3], failed verify; overwrite yields [3,4], verified')
    b.verify()

if __name__=='__main__':main()
