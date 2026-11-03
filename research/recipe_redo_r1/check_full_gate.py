"""Exercise None-photo rejection with a valid perturbed native04 record."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import runtime as rt
import struct
import zlib
from confirmation import selected
from entry_codec import CRC_FIELDS,record_checks
from full_confirm_support import gate


def main():
    path,source=selected('mount-a12',30)
    original=path.with_suffix('.record552').read_bytes()
    groups={name:rt.arrays(rt.LOCAL/'targets/mount-a12'/('30_'+name+'.npz'))
        for name in ('train','synthetic','photo_iso200','photo_other_iso')}
    positive=gate(source,original,groups,2)
    assert positive['status']=='PASS'
    changed=bytearray(original)
    for offset in range(83,114):changed[offset]=min(255,changed[offset]+3)
    for offset,size,crc_offset in CRC_FIELDS:
        struct.pack_into('>I',changed,crc_offset,zlib.crc32(changed[offset:offset+size])&0xffffffff)
    changed=bytes(changed)
    checked=record_checks(changed)
    assert checked['row_crcs_valid'] and checked['existing_row_domain_checks_pass']
    negative=gate(source,changed,groups,2)
    rows=[p for group in negative['groups'].values() for p in group['photos']]
    assert rows and all(r['source']['similarity_percent'] is None for r in rows)
    assert negative['status']=='REVIEW' and any(not r['None_absolute_gate'] for r in rows)
    folder=rt.LOCAL/'full_gate_negative_cases'
    folder.mkdir(exist_ok=False)
    (folder/'changed_native04.record552').write_bytes(changed)
    rt.dump(folder/'detail.json',dict(positive=positive,negative=negative,record_checks=checked,
        gate_only_countercase=True,not_a_recipe_candidate=True))
    rt.dump('full_confirmation_gate_checks.json',dict(status='PASS',photos=len(rows),
        identical_None_record_passes=True,valid_perturbed_None_record_rejected=True,
        mutated_record_file=str((folder/'changed_native04.record552').relative_to(rt.HERE)),
        mutated_record_sha256=checked['sha256'],detail_file=str((folder/'detail.json').relative_to(rt.HERE)),
        detail_sha256=rt.sha(folder/'detail.json'),no_DAT_candidate_created=True))
    print('None-photo gate PASS:',len(rows),'photos; valid perturbed record rejected')


if __name__=='__main__':main()
