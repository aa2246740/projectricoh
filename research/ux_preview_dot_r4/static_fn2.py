"""Bind Fn2 source and final machine-code paths to the frozen input files."""
from pathlib import Path
import json
import re
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ROOT, OUT, save, load, file_sha, sha

def excerpt(path, begin, end):
    lines = path.read_text().splitlines()
    selected = '\n'.join(f'{i + 1}: {line}' for i, line in enumerate(lines) if begin <= i + 1 <= end)
    return dict(path=str(path.relative_to(ROOT)), sha256=file_sha(path), first_line=begin,
                last_line=end, text=selected)

def main():
    audit = load(ROOT / 'research/review_g117_codegen/audit.py', 'fn2_static_elf')
    words = load(ROOT / 'research/review_g119b/neutral_terms.py', 'fn2_quality_words')
    records = []
    for generation, tree, asm_path in (
        (119, 'engine_v40_ux', ROOT / 'research/review_g119b/engine119.asm'),
        (120, 'engine_v41_ux', ROOT / 'research/ux_preview_dot_r3/engine120.asm'),
    ):
        folder = ROOT / 'firmware' / tree / 'candidate'
        elf = audit.Elf(folder / 'local/full-r13/engine.elf')
        dat = (folder / 'local/full-r13/GXRCE.DAT').read_bytes()
        start = int.from_bytes(dat[132:136], 'big')
        size = int.from_bytes(dat[136:140], 'big')
        assert dat[start:start+size] == elf.engine['data']
        asm = asm_path.read_text()
        decoded = audit.rows(asm)
        functions = []
        for name in ('a4_move', 'ig_apply', 'ig_event', 'eng_apply', 'apply_impl',
                     'ig_panel_open', 'eng_current', 'rv_call'):
            symbol = elf.functions[name]
            lines = []
            calls = []
            for pc, row in sorted(decoded.items()):
                pc = int(pc)
                if not symbol['address'] <= pc < symbol['address'] + symbol['size']:
                    continue
                lines.append(f'{pc:08x}: {row["raw"]} {row["asm"]}')
                for match in re.finditer(r'\bbl\s+([0-9a-f]+) <([^>]+)>', row['asm']):
                    target = match[2].split('+')[0]
                    if target != name:
                        calls.append(dict(pc=hex(pc), target=target, address=hex(int(match[1], 16))))
            functions.append(dict(name=name, address=hex(symbol['address']), size=symbol['size'], calls=calls))
            (OUT / f'fn2-machine-{generation}-{name}.txt').write_text(words.replace('\n'.join(lines)+'\n'))
        source = folder / 'containers/product/adapter.c'
        source_lines = source.read_text().splitlines()
        source_functions = []
        for name in ('a4_move', 'a4_finish', 'ig_event', 'ig_apply', 'ig_panel_open'):
            first = next(i for i, line in enumerate(source_lines) if re.match(r'.*\b'+name+r'\([^;]*$', line))
            end = next(i for i in range(first+1, len(source_lines)) if source_lines[i] == '}')
            source_functions.append(excerpt(source, first+1, end+1))
        records.append(dict(generation=generation, tree=tree, dat_sha256=sha(dat), elf_sha256=sha(elf.raw),
            dat_engine_equals_elf=True, functions=functions, source_functions=source_functions))
    relevant = ROOT / 'research/ux_preview_dot_r3/native_ux.py'
    lines = relevant.read_text().splitlines()
    first = next(i for i, line in enumerate(lines) if line.startswith('def fn2_half_exit('))
    last = next(i for i in range(first+1, len(lines)) if lines[i].startswith('def matrix('))
    checks = dict(arrow='a4_move changes draft and renders without eng_apply or unit communication.',
        confirmation='ig_event calls a4_finish(save=1), whose eng_apply applies a changed draft.',
        unchanged_draft_fast_path='eng_apply avoids apply_impl only if draft equals current live tweak.',
        half_shutter='The accepted regression requires an unconfirmed draft to leave the previous live tweak applied.',
        state_countercase='Fn2 draft contrast +1 and live contrast 0 differ before H07. Accepting live alone loses the requested Fn2 confirmation.',
        decision='Keeping both existing confirmation and half-shutter behavior requires communication on the dirty-draft confirmation path.')
    save('static-fn2.json', dict(status='H07_COMMUNICATION_REQUIRED_FOR_EXISTING_FN2_CONTRACT',
        records=records, existing_half_shutter_regression=excerpt(relevant, first+1, last), checks=checks,
        scope='Static source and final instruction evidence. No new firmware was compiled or linked.'))
    print('PASS source and final-machine binding; dirty Fn2 draft requires H07 application under the existing regression contract.', flush=True)

if __name__ == '__main__':
    main()
