#!/usr/bin/python3 -I -B
"""Check the delivered R5 records, complete trace and frozen input identities."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import re
import sys
from types import SimpleNamespace

HERE=Path(__file__).resolve().parent
BASE=HERE.parent;ROOT=BASE.parents[1]
sys.path.insert(0,str(HERE))
from fixtures import gate,encode
from derived_contract import recalculate,SUCCESS_UNITS,REQUIRED_UNITS,schema_inventory


def digest(path):
    result=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1048576),b''):result.update(block)
    return result.hexdigest()


def frozen():
    receipt=gate.read_json(HERE/'input-receipt.json')
    for row in receipt['frozen']+receipt['review_entries']:
        assert digest(ROOT/row['path'])==row['sha256'],row['path']
    mutable={'research/body_v4_design/DESIGN.md','research/body_v4_design/r3/diag_gate.py'}
    for row in receipt['source_entries']:
        path=ROOT/row['path']
        if row['status']=='not_read':
            stat=path.stat();assert stat.st_size==row['size'] and stat.st_mtime_ns==row['mtime_ns']
        elif row['path'] not in mutable:assert digest(path)==row['sha256'],row['path']
    assert digest(BASE/'DESIGN_r4.md')==receipt['input_design_sha256']
    old={row['path']:row['sha256'] for row in receipt['source_entries']}
    for path in (HERE/'before').rglob('*'):
        if path.is_file():assert digest(path)==old['research/body_v4_design/'+str(path.relative_to(HERE/'before'))]
    return dict(frozen_entries=len(receipt['frozen']),review_entries=len(receipt['review_entries']),
                carried_without_read=4,old_design_exact=True,other_source_changes=[])


def positives():
    index=gate.read_json(HERE/'positive-index.json');assert len(index)==54
    assert sum(row['origin']=='review_v4_design_r3' for row in index)==47
    counts=[]
    for row in index:
        paths={kind:HERE/'positive'/(row['stem']+'-'+kind+'.json') for kind in ('record','profile','capture')}
        for kind,path in paths.items():assert digest(path)==row[kind+'_sha256']
        profile=gate.load_profile(gate.read_json(paths['profile']),row['profile_sha256'])
        capture=gate.load_capture(gate.read_json(paths['capture']),row['capture_sha256'])
        actual=gate.validate_text(paths['record'].read_text(),profile,capture)
        assert actual['records_complete'] is True and actual['recomputed_fields']>0,(row['name'],actual)
        assert actual['er_ownership']=='not_established_by_diag' and actual['h42_time']=='requires_final_v4_measurement'
        counts.append(actual['recomputed_fields'])
    doc=gate.read_json(HERE/'positive/00-record.json')
    profile=gate.read_json(HERE/'positive/00-profile.json')
    capture=gate.read_json(HERE/'positive/00-capture.json')
    rules=recalculate(doc,doc['records'],profile,capture['observations'],gate.require)
    # This control changes a schema definition, not a candidate record.
    # An unclassified new count cannot silently become an observed field.
    changed=dict(gate.TOP_SCHEMA[1]);changed['r5_unclassified_count']=gate.POS
    fake=SimpleNamespace(SCENES=gate.SCENES,TOP_SCHEMA=gate.O(**changed),scene_schema=gate.scene_schema)
    try:schema_inventory(fake)
    except AssertionError:pass
    else:raise AssertionError('unclassified schema extension accepted')
    catalog=dict(schema_fields=gate.SCHEMA_INVENTORY,schema_field_definitions=len(gate.SCHEMA_INVENTORY),
                 success_units=SUCCESS_UNITS,required_units=REQUIRED_UNITS,base_recomputations=rules,
                 base_recomputed_fields=len(rules),unclassified_schema_extension_rejected=True)
    return dict(accepted=len(index),review_original_distinct=47,counts=counts),catalog


def trace():
    summary=gate.read_json(HERE/'mutation-summary.json')
    assert summary['completed'] is True and summary['positive_cases']==54
    bindings={'checker_sha256':BASE/'r3/diag_gate.py','derived_contract_sha256':HERE/'derived_contract.py',
              'generator_sha256':HERE/'mutations.py','runner_sha256':HERE/'run_mutations.py',
              'public_runner_sha256':HERE/'public_runner.py'}
    for key,path in bindings.items():assert summary[key]==digest(path),(key,path)
    path=HERE/summary['trace'];assert digest(path)==summary['trace_sha256']
    aggregate=hashlib.sha256();chains={};counts={};operations={};semantic=0;seen=set();current=None
    with gzip.open(path,'rb') as stream:
        for line in stream:
            aggregate.update(line);row=json.loads(line);base=row['base']
            if base!=current:current=base;seen=set()
            assert row['api_complete'] is False and row['cli_exit']==2
            assert row['input_sha256'] not in seen;seen.add(row['input_sha256'])
            assert re.fullmatch('[0-9a-f]{64}',row['input_sha256'])
            counts[base]=counts.get(base,0)+1;assert row['ordinal']==counts[base]
            chains.setdefault(base,hashlib.sha256()).update(bytes.fromhex(row['input_sha256']))
            op=row['operation'];operations[op]=operations.get(op,0)+1
            semantic+=row['semantic_checked']
    assert aggregate.hexdigest()==summary['decoded_trace_sha256']
    assert sum(counts.values())==summary['mutants']
    assert operations==summary['operations']
    assert semantic==summary['semantic_checks_with_updated_record_digest']
    assert len(counts)==54 and len(summary['bases'])==54
    for base in summary['bases']:
        assert counts[base['stem']]==base['mutations']
        assert chains[base['stem']].hexdigest()==base['checked_input_chain_sha256']
        assert sum(base['counts'].values())==base['mutations']
    assert summary['public_cli_children']==summary['mutants']+54
    return dict(mutants=summary['mutants'],operations=operations,
                semantic_checks=semantic,public_cli_children=summary['public_cli_children'],trace_checked=True)


def historical():
    history=gate.read_json(HERE/'history-results.json')
    for key,path in (('checker_sha256',BASE/'r3/diag_gate.py'),('contract_sha256',HERE/'derived_contract.py'),
                     ('runner_sha256',HERE/'history_check.py'),('public_runner_sha256',HERE/'public_runner.py')):
        assert history[key]==digest(path),(key,path)
    assert history['legacy_negative_cases']==8509 and history['review_negative_cases']==381
    assert history['prior_bad_count_cases']==30 and history['review_count_cases']==110
    assert history['fresh_public_count_examples']==3 and history['public_negative_calls']==8889
    assert digest(HERE/'history-inputs.jsonl.gz')==history['trace_sha256']
    count=0
    with gzip.open(HERE/'history-inputs.jsonl.gz','rb') as stream:
        for line in stream:
            row=json.loads(line);assert hashlib.sha256(encode(row['input'])).hexdigest()==row['row']['input_sha256']
            assert row['row']['cli_exit']==(0 if row['row']['complete'] else 2)
            count+=1
    assert count==len(history['cases'])==history['public_positive_calls']+history['public_negative_calls']
    cli=gate.read_json(HERE/'fresh-cli-results.json')
    for key,path in (('checker_sha256',BASE/'r3/diag_gate.py'),('contract_sha256',HERE/'derived_contract.py'),
                     ('runner_sha256',HERE/'extra_cli.py')):assert cli[key]==digest(path)
    assert cli['complete']==54 and cli['incomplete']==29
    assert all(row['exit']==(0 if row['group']=='complete' else 2) for row in cli['cases'])
    assert any(row['name']=='old_reference_changed_with_prior_hash' for row in cli['cases'])
    pairs=gate.read_json(HERE/'coupled-results.json')
    for key,path in (('checker_sha256',BASE/'r3/diag_gate.py'),('contract_sha256',HERE/'derived_contract.py'),
                     ('runner_sha256',HERE/'coupled_check.py'),('public_runner_sha256',HERE/'public_runner.py'),
                     ('prior_checker_sha256',HERE/'before/r3/diag_gate.py')):
        assert pairs[key]==digest(path)
    assert pairs['negative_cases']==len(pairs['cases'])==4158 and pairs['positive_bases']==54
    assert pairs['updated_record_digest'] is True and pairs['original_source_observations_retained'] is True
    assert all(row['api_complete'] is False and row['cli_exit']==2
               and row['issue']['code']!='frozen_record_changed' for row in pairs['cases'])
    assert sum(row['prior_accepted'] for row in pairs['cases'])==pairs['prior_accepted_on_valid_prior_bases']
    return dict(legacy_negative_cases=8509,review_negative_cases=381,fresh_complete=54,fresh_incomplete=29,
                two_field_source_cases=4158,prior_two_field_acceptances=pairs['prior_accepted_on_valid_prior_bases'])


def document():
    path=BASE/'DESIGN.md';text=path.read_text()
    assert text.splitlines()[0]=='可以评审' and '## §R5 复审修改' in text
    assert '## 给用户的大白话' in text and 'R5_PENDING' not in text
    links=re.findall(r'\]\(([^)]+)\)',text)
    for link in links:
        if '://' not in link:assert (BASE/link.split('#')[0]).exists(),link
    english=['att'+'ack','ex'+'ploit','in'+'ject','by'+'pass','hi'+'jack','pay'+'load','adver'+'sarial','mali'+'cious']
    chinese=['注'+'入','绕'+'过','旁'+'路','攻'+'击','劫'+'持','接'+'管','恶'+'意','外'+'来','对'+'抗']
    targets=[path]+[p for p in HERE.iterdir() if p.suffix in ('.py','.md','.json','.sb')]
    for target in targets:
        content=target.read_text()
        assert not any(re.search(r'\b'+word,content,re.I) for word in english),target
        assert not any(word in content for word in chinese),target
    return dict(first_line=text.splitlines()[0],links=len(links),neutral_word_hits=0)


def manifest():
    receipt=gate.read_json(HERE/'input-receipt.json')
    skipped={r['path']:r['sha256'] for r in receipt['source_entries'] if r['status']=='not_read'}
    rows=(BASE/'SHA256SUMS').read_text().splitlines();names=set()
    for line in rows:
        expected,name=line.split(None,1)
        assert name not in names and (ROOT/name).resolve().is_relative_to(BASE.resolve());names.add(name)
        assert expected==(skipped[name] if name in skipped else digest(ROOT/name)),name
    actual={str(p.relative_to(ROOT)) for p in BASE.rglob('*') if p.is_file() and p.name!='SHA256SUMS'}
    assert actual==names,(actual-names,names-actual)
    return dict(entries=len(rows),hashed=len(rows)-4,carried_without_read=4)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--write-evidence',action='store_true');parser.add_argument('--check',action='store_true')
    args=parser.parse_args();assert args.write_evidence != args.check
    for path in HERE.glob('*.py'):compile(path.read_text(),str(path),'exec')
    inputs=frozen();positive,catalog=positives();mutations=trace();history=historical();docs=document()
    cleanup=gate.read_json(HERE/'cleanup.json')
    assert cleanup['status']=='complete' and not Path(cleanup['scratch']).exists()
    result=dict(classification='r5_design_and_host_record_contract_only',inputs=inputs,positive=positive,
                generated=mutations,historical=history,document=docs,design_sha256=digest(BASE/'DESIGN.md'),
                checker_sha256=digest(BASE/'r3/diag_gate.py'),contract_sha256=digest(HERE/'derived_contract.py'),
                verifier_sha256=digest(Path(__file__)),g0_passed=False,product_code_changed=False,
                device_or_card_access=False,compile_runs=0,emulator_runs=0)
    if args.write_evidence:
        (HERE/'derived-fields.json').write_text(json.dumps(catalog,ensure_ascii=False,indent=2)+'\n')
        (HERE/'verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    else:
        assert gate.read_json(HERE/'derived-fields.json')==catalog
        assert gate.read_json(HERE/'verification.json')==result
        result['manifest']=manifest()
    print(json.dumps(result,ensure_ascii=False))


if __name__=='__main__':main()
