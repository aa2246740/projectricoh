#!/usr/bin/env python3
"""Regenerate every full fit, compare all exported bytes, and reconstruct pairs in RAM."""
import sys
from pathlib import Path
sys.dont_write_bytecode=True
sys.path.insert(0,str(Path(__file__).resolve().parent))
import core as c
import fit_round5 as fit
from build_tables import entry_for


def fields(doc):
    return {k:doc[k] for k in ('matrix_hex','colour_hex','curve_nodes','channel_curves_RGB')}


def main():
    before={f'{slot}_{level}':fields(c.read(c.LOCAL/f'fits/{slot}_{level}.json'))
            for slot in ('05','06') for level in ('a','b','c','full24')}
    for slot in ('05','06'):fit.full(slot)
    for key,prior in before.items():assert fields(c.read(c.LOCAL/f'fits/{key}.json'))==prior,key
    bank=(c.LOCAL/'inputs/firmware/stage2j/examples/DEEPISP0.DAT').read_bytes()
    checks={}
    for kind in ('test','daily'):
        folder=c.PACK/f'tables-v5-fuji-{kind}'
        blob=(folder/'DEEPTBL0.DAT').read_bytes();entries=c.src.parse(blob,bank)
        manifest=c.read(folder/'manifest.json');body=bytearray(blob[c.src.HEADER_BYTES:])
        for slot,meaning in manifest['slots'].items():
            if meaning['recipe'] not in ('05','06') or 'level' not in meaning:continue
            raw,_=entry_for(int(slot),meaning['recipe'],meaning['level'],bank,entries[0]['rows'])
            start=c.src.TABLE_SLOTS.index(int(slot))*c.src.ENTRY_BYTES
            body[start:start+c.src.ENTRY_BYTES]=raw
        regenerated=c.src.seal(blob[:12],body)
        assert regenerated==blob==(folder/'DEEPTBL1.DAT').read_bytes()
        checks[kind]={'byte_identical':True,'sha256':c.sha(folder/'DEEPTBL0.DAT')}
    c.dump(c.LOCAL/'deterministic_regeneration.json',{'full_fits_checked':8,'packages':checks})
    print('DETERMINISTIC',checks,flush=True)


if __name__=='__main__':main()
