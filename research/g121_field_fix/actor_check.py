"""Resolve observed failure stores against both exact ELF symbol tables."""
from pathlib import Path
import json
import subprocess
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import ROOT,OUT,TREE,DAT,load,save,file_sha

def main():
    reader=load(ROOT/'tools/native_harness/image_loader.py','actor_elf')
    rows=[]
    cases=[('baseline-notice.json',ROOT/'firmware/engine_v42_ux/candidate/local/full-r13/engine.elf','finish')]
    cases += [('native/notice-details-'+u+'.json',TREE/'candidate/local/full-r13/engine.elf','record_failure') for u in ('50mm','28mm','mount')]
    for name,path,symbol in cases:
        x=json.loads((OUT/name).read_text());elf=reader.Elf(path)
        state=x.get('after') or x['diagnostic']['state'];base=state['root']['code_address']-256
        changes=x['failed_writes'];assert len(changes)==1,changes
        for change in changes:
            pc=int(change['pc'],16);relative=pc-base;start=elf.symbols[symbol]
            assert start<=relative<start+512,(name,hex(relative),symbol)
            command=[str(ROOT/'research/tooling_m32r/prefix/bin/m32r-elf-objdump'),'-d',
                '--start-address='+hex(start),'--stop-address='+hex(relative+8),str(path)]
            result=subprocess.run(command,capture_output=True,text=True,check=True)
            label='baseline' if symbol=='finish' else x['unit']
            (OUT/('failure-store-'+label+'.txt')).write_text(result.stdout)
            rows.append(dict(record=name,elf_sha256=file_sha(path),runtime_pc=hex(pc),
                image_base=hex(base),relative_pc=hex(relative),symbol=symbol,symbol_start=hex(start)))
    source=(TREE/'candidate/containers/product/adapter.c').read_text()
    assert source.count('n.failed=1;')==1
    save('failure-store-actors.json',dict(status='PASS',dat_sha256=file_sha(DAT),stores=rows))
    print('PASS failure store actors',[(x['runtime_pc'],x['symbol']) for x in rows],flush=True)

if __name__=='__main__':main()
