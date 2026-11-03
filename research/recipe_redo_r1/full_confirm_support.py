"""Freeze all feasible starts and apply the reviewed per-flow exact gates."""
import hashlib
import math
import struct
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import runtime as rt
from runtime import np
from entry_codec import predict


def feasible(unit, index, target_sha):
    rows=[]
    for path in sorted((rt.LOCAL/'fits'/unit/f'{index:02d}').glob('L[01]_*.json')):
        doc=rt.read(path)
        if doc['target_sha256']!=target_sha or not doc['quality']['passes'] or not doc.get('parameters'):
            continue
        record=path.with_suffix('.record552').read_bytes()
        assert hashlib.sha256(record).hexdigest()==doc['record']['sha256']
        rows.append((path,doc,record))
    return rows


def retain(row, train, camera, current, gradients, rings, ui, guard, objective):
    path,doc,record=row
    value=objective(predict(record,train['x'],ui),train['want'],train['sw'])
    q=guard(camera,record,current,gradients,rings,ui,doc.get('gray',False))
    assert q['passes'] and abs(value-doc['objective'])<1e-10
    return dict(entry=record,objective=value,origin=doc['origin'],quality=q,
        parameters=doc['parameters'],theta=doc['theta'],axis=doc['axis'],status=doc['status'],
        gray=doc.get('gray',False),record_encoding_level=doc.get('record_encoding_level',doc['level']),
        retained_feasible_parent=str(path.relative_to(rt.HERE)))


def add_axes(axes, feasible_rows):
    for path,doc,record in feasible_rows:
        nodes=np.array([0,*struct.unpack_from('>31H',record,20),4095])
        if not any(np.array_equal(nodes,x) for _,x in axes):
            axes.append(('feasible_axis_'+doc['record']['sha256'][:10],nodes))
    return axes


def starts(primary, nodes, base_starts, feasible_rows, fast_record, seed, axis_name, manifest):
    declared=list(base_starts)
    fast_nodes=np.array([0,*struct.unpack_from('>31H',fast_record,20),4095])
    if np.array_equal(nodes,fast_nodes):
        declared.append(('fast_candidate_extra_integer',seed(primary,fast_record)))
    for path,doc,record in feasible_rows:
        x=np.array([0,*struct.unpack_from('>31H',record,20),4095])
        if np.array_equal(x,nodes):
            declared.append(('feasible:'+str(path.relative_to(rt.HERE)),seed(primary,record)))
    distinct={}
    for name,vector in declared:
        identity=hashlib.sha256(np.asarray(vector,dtype='<f8').tobytes()).hexdigest()
        if identity not in distinct:
            distinct[identity]=dict(names=[],vector=vector)
        distinct[identity]['names'].append(name)
    output=[]
    for identity,row in distinct.items():
        name=' | '.join(row['names'])
        manifest.append(dict(axis=axis_name,nodes=nodes,start_names=row['names'],
            vector_sha256=identity,vector=row['vector'],identical_starts_share_one_run=True,
            model_config=primary.config,lower=primary.lower,upper=primary.upper))
        output.append((name,row['vector']))
    return output


def noise(prediction,want,weight):
    error=rt.delta_e00(rt.lab_from_codes(prediction),rt.lab_from_codes(want))
    terms=weight*error*error
    values=[float(np.mean(terms)/np.mean(weight)),float(np.sum(terms)/np.sum(weight)),
            math.fsum(map(float,terms))/math.fsum(map(float,weight))]
    return dict(reductions=values,tolerance=max(16*abs(float(np.spacing(values[0]))),
        8*max(abs(x-values[0]) for x in values),1e-14),fixed_reference_pixels=True)


def gate(source,final,groups,ui):
    record=(rt.HERE/source['record_path']).read_bytes()
    details={}
    for group,data in groups.items():
        if not group.startswith('photo_') or not len(data['x']):
            continue
        before=predict(record,data['x'],ui);after=predict(final,data['x'],ui)
        rows=[]
        for ident in sorted(set(map(int,data['photo_id']))):
            use=data['photo_id']==ident
            a=rt.score(data['base'][use],before[use],data['want'][use])
            b=rt.score(data['base'][use],after[use],data['want'][use])
            same_none=(a['similarity_percent'] is None)==(b['similarity_percent'] is None)
            assert same_none
            tol={key:max(32*abs(float(np.spacing(a['de00'][key]))),1e-13) for key in ('median','p95')}
            absolute=all(b['de00'][key]<=a['de00'][key]+tol[key] for key in tol)
            rows.append(dict(photo_id=ident,source=a,exact=b,None_absolute_gate=absolute,
                absolute_tolerance=tol))
        available=[r for r in rows if r['source']['similarity_percent'] is not None]
        missing=[r for r in rows if r['source']['similarity_percent'] is None]
        old=float(np.median([r['source']['similarity_percent'] for r in available])) if available else None
        new=float(np.median([r['exact']['similarity_percent'] for r in available])) if available else None
        similarity_ok=not available or new>=old-.1-1e-12
        details[group]=dict(photos=rows,source_photo_similarity_median=old,
            exact_photo_similarity_median=new,selected_L1_similarity_drop_limit_pp=.1,
            finite_similarity_gate=bool(similarity_ok),None_per_photo_absolute_gate=all(r['None_absolute_gate'] for r in missing),
            passed=bool(similarity_ok and all(r['None_absolute_gate'] for r in missing)))
    if not details:
        data=groups['synthetic'];a=rt.score(data['base'],predict(record,data['x'],ui),data['want'])
        b=rt.score(data['base'],predict(final,data['x'],ui),data['want'])
        passed=(b['similarity_percent']>=a['similarity_percent']-.1-1e-12 if a['similarity_percent'] is not None
            else all(b['de00'][k]<=a['de00'][k]+max(32*abs(float(np.spacing(a['de00'][k]))),1e-13) for k in ('median','p95')))
        details['synthetic_only']=dict(source=a,exact=b,passed=bool(passed),photo_contract_not_claimed=True)
    return dict(status='PASS' if all(r['passed'] for r in details.values()) else 'REVIEW',
        groups=details,per_unit_target_group_checks=True,real_photo_groups_used=ui!=1,
        None_is_not_replaced_with_zero_or_hundred=True)
