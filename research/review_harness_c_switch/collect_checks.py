from pathlib import Path
import json

OUT = Path(__file__).resolve().parent


def read(relative):
    return json.loads((OUT / relative).read_text())


def main():
    protocols = []
    for name, count in [('independent', 15), ('extended', 4), ('new', 6), ('trace', 6), ('mro', 19)]:
        data = read('entry/local/gates/cases/local/' + name + '-summary.json')
        rows = data['checks']
        passed = (data['cases'] == count and len(rows) == count and
                  data.get('mismatches', 0) == 0 and
                  all(row.get('equal') is True and row.get('passed', True) is True and
                      row.get('guard_fallback', True) is True and not row.get('differences') for row in rows))
        protocols.append({'suite': name, 'cases': count, 'passed': passed})
    differential = read('entry/local/gates/differential/summary.json')
    boundaries = read('entry/local/gates/round2/audit-checks/summary.json')
    changes = read('entry/local/gates/audit-changes.json')
    warm = read('warm-audit/summary.json')
    errors = read('errors/summary.json')
    outside = {'write-trace-negative-low', 'write-trace-large-high', 'write-trace-negative-unused'}
    valid_errors = [row for row in errors['checks'] if row['case'] not in outside]
    controls = read('switch/summary.json')
    mutations = read('evidence/mutations.json')
    resume = read('identity-args-r2/summary.json')
    globals_ = read('global-resolution/summary.json')
    validation = read('event-validation/summary.json')
    event_entry = read('event-entry/summary.json')
    result = {
        'protocols': protocols,
        'protocol_cases': sum(row['cases'] for row in protocols),
        'protocols_passed': all(row['passed'] for row in protocols),
        'instruction_cases': differential['instruction_cases'],
        'instruction_boundaries': len(differential['boundary_cases']),
        'instructions_passed': differential['instruction_cases'] == 6080 and len(differential['boundary_cases']) == 40 and differential['failures'] == 0,
        'audit_boundaries': boundaries['cases'],
        'audit_boundaries_passed': boundaries['cases'] == 90 and all(row['passed'] is True for row in boundaries['checks']),
        'runtime_changes': changes['cases'],
        'runtime_changes_passed': changes['cases'] == 17 and all(row['passed'] is True for row in changes['checks']),
        'warm_changes': warm['cases'],
        'warm_changes_passed': warm['cases'] == 6 and all(row['passed'] is True for row in warm['checks']),
        'valid_error_cases': len(valid_errors),
        'valid_error_cases_equal': len(valid_errors) == 20 and all(row['equal'] is True for row in valid_errors),
        'outside_contract_cases': [{'case': row['case'], 'equal': row['equal']} for row in errors['checks'] if row['case'] in outside],
        'switch_controls_passed': controls['passed'],
        'switch_controls': len(controls['checks']),
        'native_mutations_detected': mutations['passed'] and all(row['detected'] for row in mutations['checks']),
        'resume_source_change_difference_confirmed': all(resume[key] is True for key in [
            'changed_driver_reused_old_pass', 'current_input_fresh_python_fails',
            'current_input_fresh_c_fails', 'same_current_driver_sha256']),
        'fresh_fail_json_equal': read('identity-args-r2/fresh-error-comparison.json')['equal'],
        'busy_function_json_equal': read('busy-diagnostic/comparison.json')['equal'],
        'writeevent_binding_mismatches': globals_['mismatches'],
        'writeevent_controls_confirmed': globals_['cases'] == 5 and globals_['mismatches'] == 3 and globals_['checks'][0]['equal'] and globals_['checks'][-1]['equal'],
        'writeevent_c_pass_python_fail_confirmed': validation['c_pass_python_fail'] and validation['filter_off_equal'],
        'writeevent_entry_c_pass_python_fail_confirmed': event_entry['fresh_c_pass_python_fail'],
        'candidate_accepted': False,
        'blocking_findings': ['P1-01: g139 OBSERVED_P1 versus FAIL', 'P1-02: changed test source reuses saved PASS', 'P1-03: WriteEvent global binding changes are missed by fast writes'],
    }
    required = ['protocols_passed', 'instructions_passed', 'audit_boundaries_passed',
                'runtime_changes_passed', 'warm_changes_passed', 'valid_error_cases_equal', 'switch_controls_passed',
                'native_mutations_detected', 'resume_source_change_difference_confirmed',
                'fresh_fail_json_equal', 'busy_function_json_equal',
                'writeevent_controls_confirmed', 'writeevent_c_pass_python_fail_confirmed',
                'writeevent_entry_c_pass_python_fail_confirmed']
    result['evidence_checks_complete'] = all(result[key] for key in required)
    (OUT / 'evidence/check-results.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))
    return 0 if result['evidence_checks_complete'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
