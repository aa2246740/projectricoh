"""Validate review evidence, scope and the final delivery manifest."""
import json
import re
import subprocess
from collections import Counter
import review as c
import checks as q

def finalize():
    q.byte_checks()
    sets={}
    for key,name in [('legacy','acceptance-results'),('independent','independent-attacks'),('extra','extra-regressions'),('old_dat','old-DAT-explicit-save')]:
        rows=json.loads((c.LOCAL/(name+'.json')).read_text())
        assert rows and all(r['rc']==0 for r in rows),name
        sets[key]=rows
    faults={k:json.loads((c.LOCAL/('faults-'+k+'.json')).read_text()) for k in ('last','tweak')}
    assert len(faults['last']['cases'])==744 and len(faults['tweak']['cases'])==840
    assert all(r['rc']==0 for x in faults.values() for r in x['cases'])
    assert [len(sets[k]) for k in ('legacy','independent','extra','old_dat')]==[232,844,204,4]
    reflexive=[];deferred=[];power=[];snapshots=[]
    for row in sets['independent']:
        log=(c.HERE/row['log']).read_text()
        if row['name']=='reflexive' and 'COUNTEREXAMPLE' in log:
            assert 'generation=2 creates=1 renames=1' in log;reflexive.append(row['log'])
        if row['name']=='deferred' and 'changed_last_lost=1' in log:deferred.append(row['log'])
        if row['name']=='power':power.append(log.splitlines()[0])
        if row['name']=='crash-snapshots':snapshots.append(int(re.search(r'CRASH_PASS images=(\d+)',log)[1]))
    assert len(reflexive)==56 and len(deferred)==224 and snapshots==[46]*4
    assert len(power)==64 and sum('accepted_03_BW_residue' in s for s in power)==4
    getter=json.loads((c.LOCAL/'getter-execution.json').read_text());assert len(getter)==256
    assert c.sha(c.CARD)=='ff1a4d32a23456464e340ac6cf67f95a582a58e61f2860f21e070c1b1509b237'
    assert c.CARD.stat().st_size==62228 and q.u32(c.CARD.read_bytes(),28)==109
    summary=dict(verdict='不可以上卡',candidate_sha256=c.sha(c.CARD),generation=109,
        host_runs_reported=sum(len(x) for x in sets.values())+sum(len(x['cases'])+len(x['traces']) for x in faults.values()),
        successful_safety_and_characterization_assertions=True,all_runs_are_not_safety_passes=True,
        phase_counts={k:len(v) for k,v in sets.items()},
        independent_scenarios=dict(Counter(r['name'] for r in sets['independent'])),
        fault_injections={k:len(x['cases']) for k,x in faults.items()},fault_baselines=6,
        persistent_highlight_overwrites=len(reflexive),deferred_choices_lost=len(deferred),
        crash_file_images=sum(snapshots),native_getter_inputs=256,
        C_and_Python_vector_slots=144,r6_r7_unchanged_slots=48,
        camera_acceptance=False,candidate_M32R_executed=False,physical_power_cut=False)
    c.save(c.LOCAL/'test-summary.json',summary)
    findings=[dict(id='R7-01',priority='P1',blocking=True,kind='inherited_highlight_has_GXLS_persistence_consequence',logs=reflexive),
              dict(id='R7-02',priority='P2',blocking=False,kind='old_DAT_explicit_GXTS_save_not_zero_writes',logs=[r['log'] for r in sets['old_dat']]),
              dict(id='R7-03',priority='P2',blocking=False,kind='unclosed_selection_lost_and_old_full_memory_restored',logs=deferred),
              dict(id='R7-04',priority='P2',blocking=False,accepted_by_brief=True,kind='recipe_03_native_BW_survives_without_GXLS')]
    c.save(c.LOCAL/'findings.json',findings)
    c.save(c.LOCAL/'power-cycle-results.json',dict(default_recipe_cases=power,all_other_native_S_bytes_unchanged=True,
        selectors={'01,02,04,05,06,07,08':1,'03':3},WB_defaults=[9,9],BW_parameters={'0x645':3,'0x646':4},
        dormant_BW_parameters_not_erased_by_Standard=True,unclosed_different_choice_restores_full_older_memory=224,
        physical_persistence_unverified=True))
    before=(c.LOCAL/'git-tracked-before.txt').read_text().splitlines()
    after=subprocess.check_output(['git','--no-optional-locks','status','--porcelain=v1','--untracked-files=no'],cwd=c.ROOT,text=True).splitlines()
    normalize=lambda rows:[r for r in rows if r[3:]!='decisions.tsv']
    assert normalize(before)==normalize(after)
    count=c.unchanged()
    c.save(c.LOCAL/'scope.json',dict(write_root=str(c.HERE),protected_inputs=count,protected_inputs_unchanged=True,
        tracked_status_unchanged_except_decisions=True,decisions_excluded=True,no_firmware_rebuild=True,
        no_candidate_repackage=True,no_camera_or_card_access=True,no_subagents=True,no_package_installs=True,
        no_commit_or_push=True,no_sleep_or_polling_loops=True))
    c.save(c.LOCAL/'delivery-validation.json',dict(verdict=summary['verdict'],candidate_sha256=c.sha(c.CARD),
        generation=109,blocking_findings=['R7-01'],accepted_limits=['R6-01_highlight_only','F02','03_BW'],
        source_review_and_host_evidence_only=True,local_ignored=True,protected_inputs=count))
    paths=sorted(p for p in c.HERE.rglob('*') if p.is_file() and p.name!='SHA256SUMS')
    assert not any(p.is_symlink() for p in paths)
    c.write(c.HERE/'SHA256SUMS',''.join(c.sha(p)+'  '+str(p.relative_to(c.HERE))+'\n' for p in paths))
    q.check_delivery()
    print(json.dumps(summary,ensure_ascii=False))
