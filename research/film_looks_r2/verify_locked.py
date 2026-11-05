"""Verify shared-curve flags7 payloads for the proposed locked styles, not a DAT."""
from pathlib import Path
import hashlib
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import common as C
import host_flags
import promote_probe


def main():
    summary=C.read(C.LOCAL/'summary.json');assert summary['complete']
    results=[];total=0;maximum=0.
    for item in summary['locked_Looks']:
        for ui,unit in enumerate(C.UNITS):
            row=item['units'][unit]['Look'];b=Path(row['record_file']).read_bytes()
            assert C.sha(row['record_file'])==row['sha256'] and b[1]==1
            promoted=promote_probe.promote(b,1<<ui,C.codec)
            if item['kind']=='style':
                index=14 if item['key']==53 else 3000+10*item['key']
            else:
                film=C.read(C.LOCAL/'catalog.json')['films'][item['key']]
                doc=C.read(C.LOCAL/'analysis'/f'{item["key"]:02d}'/unit/'final.json')
                index=film['indices'][doc['selected_Look_route']]
            meta=C.read(C.LOCAL/'targets'/unit/f'{index:02d}'/'profile.json')
            points=0;local_max=0.
            for key,source in meta['groups'].items():
                values=C.arrays(source)
                a=C.predict(b,values['x'],ui);p=C.predict(promoted,values['x'],ui)
                difference=float(abs(a-p).max());assert difference==0.
                points+=len(a);local_max=max(local_max,difference)
            train=C.arrays(meta['groups']['train'])
            knobs=host_flags.compare_shared_promotion(C,b,promoted,unit,train['x'][:64])
            dest=C.LOCAL/'locked_shared_flags7'/item['wire_name']/unit/'Look.record552'
            dest.parent.mkdir(parents=True,exist_ok=True)
            if dest.exists():assert dest.read_bytes()==promoted,'Preserve an exported payload; version changes'
            else:dest.write_bytes(promoted)
            result=dict(name=item['name'],wire_name=item['wire_name'],unit=unit,semantic_curves=1,
                original_flags1_sha256=row['sha256'],record_file=str(dest),record_sha256=C.sha(dest),
                flags=7,type26_control=0,base_slot=promoted[0],base_flags_required=7,
                unit_mask=1<<ui,R_G_B_identical=True,additional_curve_rows=0,additional_fitted_curve_parameters=0,
                default_points=points,default_maximum_RGB_difference=local_max,knob_equivalence=knobs,
                output_quantization_equivalence='Exact same unquantized RGB, therefore identical under all128 declared output hypotheses',
                primary_model_ISO=200,
                requires_unchanged_Standard_base_selector_parameters_WB_and_knob_metadata=True,
                no_g158_DAT_or_camera_admission=True)
            results.append(result);total+=points;maximum=max(maximum,local_max)
    C.dump('locked_shared_flags7_handoff.json',dict(schema='gxr-locked-shared-format7/1',
        status='PASS_MODEL_AND_HOST_MATH',logical_styles=len(summary['locked_Looks']),records=results,
        points_compared=total,maximum_RGB_difference=maximum,
        parser_positive_probe='promote_shared_parser_probe.json',
        no_extra_independent_Look_curve_parameters=True,no_engine_L1_expansion=True,
        scope='Candidate payloads and fixed metadata contract; Studio atomic rebuilding, full DAT/host lifecycle and camera remain pending'))
    print('LOCKED FLAGS7 EQUIVALENCE PASS',len(results),'records;',total,'points; max',maximum,flush=True)


if __name__=='__main__':main()
