"""Apply the explicit 2026-11-03 owner confirmation, without changing numeric inputs."""
from pathlib import Path
import datetime
import json

HERE=Path(__file__).resolve().parent


def write(path,value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')


def main():
    root=HERE/'local/new7'
    path=root/'owner_identity_decision.json'
    previous=root/'owner_identity_decision_before_confirmation.json'
    if not previous.exists():
        previous.write_bytes(path.read_bytes())
    decision=dict(created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        confirmation_date='2026-11-03',source='机主口头确认，由用户转达',frames='R8051894-R8051900',
        owner_confirmed_all_seven=True,all_selected_04_Std=True,no_recipe_or_fine_adjustment_between_frames=True,
        status='owner_confirmed_native04',eligible_for_04_calibration=True,
        admit_to_04_calibration_training=True,current_group_assignment='whole new outer holdout',
        used_for_current_04_training=False,used_to_change_current_recipe_parameters=False,
        white_balance='daylight preset, owner confirmed; retain WB EXIF=1 and per-file AsShotNeutral',
        light='fluorescent plus window light indoors, with exterior window views in the same capture session',
        unknown_card='ordinary scene only, never a standard colour reference',
        probes_1878_1893_excluded=True)
    write(path,decision)
    materials=json.loads((root/'materials.json').read_text())
    for row in materials:
        row.update(stock04_status='owner_confirmed_native04',recipe_label='04',
            stock04_reason='Owner confirmed all seven selected 04 Std with no intervening recipe or fine adjustment',
            identity_evidence='local/new7/owner_identity_decision.json',identity_source='机主口头确认',
            identity_confirmation_date='2026-11-03',calibration_role='primary_iso200',
            current_calibration_assignment='outer_holdout_whole_session',
            current_04_training_used=False,white_balance_name='daylight preset, owner confirmed',
            light_group='fluorescent_plus_window_and_exterior_views_same_daylight_preset_session',
            unknown_chart_treated_as_ordinary_scene=True,known_colour_references_used=False)
    write(root/'materials.json',materials)
    main_path=HERE/'local/materials.json'
    existing=json.loads(main_path.read_text())
    by_path={r['path']:r for r in existing}
    by_path.update({r['path']:r for r in materials})
    write(main_path,list(by_path.values()))
    summary_path=HERE/'new7_identity_summary.json'
    summary=json.loads(summary_path.read_text())
    summary.update(owner_cannot_confirm_per_frame=False,owner_confirmed_all_seven=True,
        admitted_to_04_calibration=True,eligible_for_04_training=True,used_for_current_04_training=False,
        owner_decision=decision,stock04_admission='Owner-confirmed native04; all seven retained as one new outer holdout',
        confirmation_source='机主口头确认，2026-11-03')
    for result in summary['results']:
        result.update(independent_04_confirmation=True,admitted_to_calibration=True,
                      used_for_current_04_training=False,white_balance='daylight preset')
    write(summary_path,summary)
    run_path=HERE/'local/continuation.json'
    run=json.loads(run_path.read_text())
    run.update(new7_owner_confirmed04=True,new7_eligible_for_04_calibration=True,
               new7_admitted_to_04_training=False,new7_current_assignment='whole-session outer holdout')
    write(run_path,run)
    replacements={
        '新增1894–1900共7对身份仍未确认，不进入04标定训练，仅作独立诊断或RAW留出；白平衡按文件手动/预设字段记录。':
        '新增1894–1900共7对已由机主口头确认原厂04，日光预设。当前整组作外层留出，尚未用于改写冻结标定或配方参数。',
        '这7对仍为04身份未确认，只作独立诊断或RAW电脑留出，不进04标定训练。':
        '这7对已升级为机主确认的原厂04，确认来源为机主口头确认，2026-11-03；当前整组作新的标定外层留出。',
        '机主收到过选回04、不调微调、自动白平衡的步骤，但没有逐张确认。':
        '机主现已确认7对均在04 Std下拍摄，期间未切配方或微调，白平衡全程日光预设。',
        '以下为冻结模型与相机JPG的响应诊断，不能称为已知原厂04标定准确率。':
        '以下为冻结模型与现已由机主确认的原厂04 JPG的比较；这些JPG没有参与冻结模型拟合。',
        '分类间隔未达到预设0.75 ΔE00门槛，且机主未确认，因此不升级用途。':
        '此前分类间隔未达到预设0.75 ΔE00门槛，未据模型升级用途；本次升级依据独立的机主确认。',
    }
    for name in ('REPORT.md','MOUNT_STAGE.md','NEW7_DIAGNOSTIC.md','PROGRESS.md'):
        path=HERE/name
        text=path.read_text()
        for before,after in replacements.items():
            text=text.replace(before,after)
        if name=='PROGRESS.md':
            text+='\n2026-11-03机主已口头确认1894–1900全为原厂04、无配方或微调变化、全程日光预设。7对升级为可用于04标定，当前整组作新外层留出，冻结输入和配方参数暂未改写。\n'
        path.write_text(text)
    with (HERE/'local/decisions.tsv').open('a') as stream:
        stream.write('\t'.join([decision['created_utc'],'new7-confirmation',
            'Upgrade seven pairs to owner-confirmed native04 and keep the entire session as a new outer holdout',
            'The owner explicitly confirmed all seven 04 selections, no adjustments, and daylight WB',
            'local/new7/owner_identity_decision.json','eligible for calibration; frozen numerical inputs unchanged'])+'\n')
    print('Seven pairs upgraded to owner-confirmed native04; current assignment: whole-session outer holdout')


if __name__=='__main__':
    main()
