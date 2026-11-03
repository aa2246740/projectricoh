"""Check handoff identities and write a repository-relative SHA256 manifest."""
from pathlib import Path
import ast
import datetime
import hashlib
import json
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import audit

IDENTITIES = (
    'inputs-before.json',
    'additional-inputs-before.json',
    'replay-inputs.json',
    'review-record-inputs.json',
)
NONAUTHORITATIVE_SOURCE = 'tools/gxr_emulator/observe.py'


def load(name):
    return json.loads((audit.OUT / name).read_text())


def sha(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def main():
    audit.preflight()
    expected = {}
    for name in IDENTITIES:
        for row in load(name):
            if row['path'] in expected:
                assert expected[row['path']] == row['sha256'], row['path']
            expected[row['path']] = row['sha256']
    current = {}
    changed = []
    for rel, original in sorted(expected.items()):
        path = audit.ROOT / rel
        assert path.is_file(), rel
        value = sha(path)
        current[rel] = value
        if value != original:
            changed.append(dict(path=rel, before_sha256=original, current_sha256=value,
                                size=path.stat().st_size))
    assert {row['path'] for row in changed} <= {NONAUTHORITATIVE_SOURCE}, changed
    after = load('inputs-after.json')
    assert {row['path'] for row in after if not row['unchanged']} == {
        row['path'] for row in changed if row['path'] in {r['path'] for r in load('inputs-before.json')}
    }

    evidence = load('evidence.json')
    assert evidence['status'] == 'PASS_STATIC' and evidence['checked_facts'] == 110
    assert evidence['fixed_setter_call_sites'] == 68 and evidence['ui_state_tables'] == 106
    assert not any(evidence[key] for key in ('camera_execution', 'new_firmware', 'new_dat'))
    binding = load('local/resident-elf-binding.json')
    assert binding['status'] == 'PASS' and len(binding['sections']) == 2
    fragments = load('local/key-fragments.json')
    assert fragments['status'] == 'PASS_HOST_FRAGMENTS' and len(fragments['cases']) == 6
    assert [row['logical_event'] for row in fragments['cases']] == [31, 89, 60, 32, 90, 61]
    for row in fragments['cases']:
        assert row['queue_notification'] == dict(queue=1, size=2, wait=0, contents='0000')
        assert not row['watched_native_entries']
    callers = load('local/callers.json')
    setter = next(row for row in callers if row['target'] == 0x20268768)
    assert len(setter['fixed_callers']) == 68
    assert len({row['owner_candidate'] for row in setter['fixed_callers']}) == 25
    assert len(load('local/ui-selected-callbacks.json')) == 72

    links = []
    for path in sorted(audit.OUT.glob('*.md')):
        for target in re.findall(r'\]\(([^)]+)\)', path.read_text()):
            if target.startswith(('https://', 'http://', '#')):
                continue
            local = (path.parent / target.split('#', 1)[0]).resolve()
            assert local.is_relative_to(audit.OUT) and local.is_file(), (path.name, target)
            links.append(dict(document=path.name, target=target))
    scripts = sorted(audit.OUT.glob('*.py'))
    for path in scripts:
        ast.parse(path.read_text(), filename=path.name)
    outputs = sorted(path for path in audit.OUT.rglob('*') if path.is_file())
    assert not any(path.is_symlink() for path in audit.OUT.rglob('*'))
    assert not any(path.suffix.lower() == '.dat' for path in outputs)
    assert (audit.OUT / 'REPORT.md').read_text().splitlines()[0] == '未定'
    result = dict(
        status='PARTIAL_SOURCE_DRIFT' if changed else 'PASS_IDENTITIES',
        utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        initial_inputs=len(load('inputs-before.json')),
        initial_unchanged=sum(row['unchanged'] for row in after),
        unique_input_identities=len(expected),
        unchanged_input_identities=len(expected) - len(changed),
        changed_inputs=changed,
        protected_input_identities_unchanged=True,
        baseline_check_passed=not changed,
        static_checks=evidence['checked_facts'], host_fragment_cases=len(fragments['cases']),
        resident_sections=len(binding['sections']), setter_call_sites=68, setter_parent_groups=25,
        ui_state_tables=106, ui_selected_callback_slots=72,
        python_syntax_files=len(scripts), markdown_link_checks=links,
        camera_execution=False, rtos_scheduling_in_this_run=False,
        new_firmware=False, new_dat=False,
        limitation='The shared observer source changed. Historical identities are retained. '
                   'Manifest hashes describe handoff files, not unchanged historical sources or RTOS reachability.'
    )
    audit.save('integrity.json', result)
    outputs = sorted(path for path in audit.OUT.rglob('*') if path.is_file() and path.name != 'SHA256SUMS')
    manifest = {str(path.relative_to(audit.ROOT)): sha(path) for path in outputs}
    manifest.update(current)
    text = ''.join(value + '  ' + rel + '\n' for rel, value in sorted(manifest.items()))
    (audit.OUT / 'SHA256SUMS').write_text(text)
    print(json.dumps(dict(status=result['status'], manifest_entries=len(manifest),
                          changed_inputs=len(changed), protected_input_identities_unchanged=True,
                          static_checks=110, host_fragment_cases=6)))


if __name__ == '__main__':
    main()
