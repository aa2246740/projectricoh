"""Expose the remaining gap to the gen117 per-PC branch closure standard.

Passing a bounded differential is evidence, not a disposition for its omitted
outcomes. Preserve those outcomes without inventing an unreachable/C proof.
"""
from pathlib import Path
import json
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import OUT, save


def main():
    coverage = json.loads((OUT / 'branch-coverage.json').read_text())
    closure = json.loads((OUT / 'codegen-closure.json').read_text())
    decoders = {str(g): json.loads((OUT / f'decode{g}.json').read_text()) for g in (118, 119)}
    opened = []
    complete = []
    functions = []
    for name, pair in sorted(coverage['functions'].items()):
        count = 0
        for gen, record in pair.items():
            decode = decoders[str(gen)]
            for branch in record['uncovered']:
                pc = int(branch['pc'], 16)
                row = decode.get(str(pc)) or decode.get(str(pc & ~3))
                assert row, (name, gen, branch)
                parts = re.split(r' -> | \|\| ', row['asm'])
                asm = parts[1] if pc & 2 and len(parts) == 2 else parts[0]
                opened.append(dict(function=name, generation=int(gen), pc=branch['pc'],
                    taken=branch['taken'], asm=asm, status='OPEN',
                    reason='Not observed by the retained-body B runs or directed cases. No per-PC C projection or frozen-invariant proof has been established.',
                    evidence=['branch-coverage.json', closure['B'][
                        'panel_render.constprop.0' if name == 'panel_render' else name]['file']]))
                count += 1
        if not count:
            complete.append(name)
        functions.append(dict(function=name, open_outcomes=count))
    assert opened, 'Reassess this self-check if all outcomes have acquired evidence.'
    save('codegen-selfcheck.json', dict(status='INCOMPLETE_GEN117_BRANCH_CLOSURE',
        artifacts=coverage['artifacts'], typed_symbols=len(closure['obligations']),
        changed_shared_symbols=sum(x['status']=='changed' for x in closure['obligations']),
        A_B_C_inventory_status=closure['status'], B_pairs=closure['B_pairs'],
        dependency_targets_unresolved=closure['unresolved'],
        fully_observed_B_functions=complete, functions=functions,
        open_outcomes=len(opened), outcomes=opened,
        conclusion='A evidence and bounded B/C evidence are retained. This is not the fully closed A/B/C result accepted in review_g117_codegen_r2.',
        remaining_work='For each OPEN outcome, execute a distinguishing case or supply an exact machine/source C cutpoint or a proved frozen-image invariant. Re-run the affected checks and regenerate the closure. No firmware change is implied by an unexecuted outcome.'))
    print('INCOMPLETE gen117 branch closure:', len(opened), 'outcomes in',
          sum(x['open_outcomes'] > 0 for x in functions), 'B functions; completed observations unchanged.', flush=True)


if __name__ == '__main__':
    main()
