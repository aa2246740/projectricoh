#!/usr/bin/env python3
"""保存当前产品的相关源码行和只读来源哈希。"""
import runpy
from pathlib import Path

S=runpy.run_path(str(Path(__file__).with_name('study.py')))
ROOT=S['ROOT']
BASE='firmware/engine_v38_b36/'
FILES={
    BASE+'candidate/containers/product/src/firmware/engine/core/eng_core.c':[(70,104),(170,223)],
    BASE+'candidate/containers/product/src/firmware/engine/core/eng_data.c':[(1,22),(37,77)],
    BASE+'candidate/containers/product/src/firmware/card_container_v2/semantic.c':[(1,25),(170,184)],
    BASE+'candidate/engine_services/services.c':[(323,338)],
    BASE+'candidate/engine_services/bridges.S':[(59,90)],
    'research/t_persistence/REPORT.md':[],
    'research/hw_mining_r2/validation/VALIDATION.md':[],
    'research/hw_mining_r2/gpt/REPORT.md':[],
    'research/gr_complete_pipeline/grd4_mode_mapping.json':[],
    'research/gr_firmware/data/unpack_manifest.json':[],
    'research/frame_gr2/color_pipeline/evidence/official-strings.tsv':[],
    'research/frame_gr2/color_pipeline/evidence/official-b01firm8.dec.bin':[],
    'artifacts/downloads/gr3-film-mods/repo/FINDINGS.md':[],
}

def main():
    sources={};snippets=[]
    for rel,ranges in FILES.items():
        p=ROOT/rel;b=p.read_bytes();sources[rel]=S['sha'](b)
        if ranges:
            lines=b.decode().splitlines()
            snippets.append('FILE '+rel)
            for a,z in ranges:
                snippets.extend(f'{no}: {lines[no-1]}' for no in range(a,min(z,len(lines))+1))
            snippets.append('')
    for p in sorted((ROOT/'research/gr_complete_pipeline/grd4_evidence').glob('sec*.asm.txt')):
        sources[str(p.relative_to(ROOT))]=S['sha'](p.read_bytes())
    S['save']('evidence/source-inputs.json',sources)
    S['write']('evidence/product-source-lines.txt','\n'.join(snippets)+'\n')
    print('已保存相关源码行及来源哈希。')

if __name__=='__main__':
    main()
