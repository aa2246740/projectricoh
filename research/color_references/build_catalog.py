#!/usr/bin/env python3
"""Build source/probe catalog without copying proprietary originals."""
from pathlib import Path
import hashlib,json,sys
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]

def save(name,data):
    (HERE/name).write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False)+'\n')

def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        while block:=f.read(1024*1024):h.update(block)
    return h.hexdigest()

def main():
    dcp=json.loads((HERE/'adobe_gr_profiles.json').read_text())
    dcp4=json.loads((HERE/'adobe_gr4_profiles.json').read_text()) if (HERE/'adobe_gr4_profiles.json').exists() else {'profiles':[]}
    refs={
      'bastibe_gr3':{'url':'https://github.com/bastibe/Darktable-Film-Simulation-Panel/tree/d6effd55cf37ce208c24cf8d072ac14028ca289b',
        'commit':'d6effd55cf37ce208c24cf8d072ac14028ca289b','exists':'已验证: API tree and four downloaded original files',
        'camera':'RICOH GR III','firmware_by_mode':{'Standard':'1.60','Positive Film':'1.60','Negative Film':'1.71'},
        'mode_verification':'MakerNote ImageTone 256/262/267, cross-checked with ExifTool author definitions',
        'settings':{'iso':100,'f_number':5.6,'exposure_seconds':.002,'date':'2023:02:19 13:21:27','WB_record':'Auto, shifts 0,0; same RGGB levels; author describes white-paper WB',
                    'all_image_control_sliders':None},
        'maps':'14-bit DNG camera RGB -> same-capture in-camera developed sRGB JPEG',
        'reference_frame':'scene-linear sensor input -> display-referred output','credibility':'high for the observed patches and exact versions; limited outside them',
        'gaps':['one chart, one daylight spectrum and exposure','all sliders not decoded or attested','no Hi-Contrast B&W','restricted original JPEG-lossless decoder lacks independent confirmation'],
        'license':'code public domain per author; photograph license not separately explicit; images retained only in scratch',
        'derived_file':'gr3_reference_measurements.json','derived_chart_csv':'gr3_chart_targets.csv'},
      'adobe_dcp':{'url':'https://helpx.adobe.com/camera-raw/desktop/dng-and-file-formats/adobe-dng-converter.html',
        'artifact_url':'https://download.adobe.com/pub/adobe/dng/mac/DNGConverter_16_5.pkg','exists':'已验证: official pkg downloaded and expanded, 21 GR III/IIIx DCP files parsed',
        'camera':['Ricoh GR III','Ricoh GR IIIx'],'firmware':None,'profile_version':'16.5 distribution, IIIx legacy and v2 variants',
        'maps':'matching camera RAW -> D50 colorimetry, ProPhoto HSV LookTable and tone curve; independent implementation approximates display sRGB',
        'reference_frame':'scene-referred camera input with display rendering stages','credibility':'Adobe camera-matching implementation, not vendor firmware',
        'gaps':['camera firmware and exact original camera slider state undocumented','Hard Monotone is not Hi-Contrast B&W','GR IV is newer than this package','independent renderer does not emulate ACR defaults'],
        'license':'Adobe proprietary; package EULA and copyright retained in scratch; no original profile redistribution',
        'derived_file':'adobe_gr_profiles.json','block_hash_file':'dcp_block_digests.json'},
      'adobe_support_table':{'url':'https://helpx.adobe.com/camera-raw/desktop/dng-and-file-formats/camera-raw-plug-supported-cameras.html',
        'exists':'已验证: live official camera support table read 2026-10-16','camera_matching':{'GR (2013)':False,'GR II':False,'GR III':True,'GR IIIx':True,'GR IV':True},
        'GR_IV_minimum_camera_raw':'17.5','maps':None,'reference_frame':None,'credibility':'official availability evidence only',
        'gaps':['does not list the name or numerical transform of each GR IV profile'],'license':'Adobe website terms'},
      'gr4_official':{'url':'https://www.ricoh-imaging.co.jp/english/products/gr-4/ex/','exists':'已验证: page and Positive/Negative full JPEG downloads',
        'camera':'RICOH GR IV','firmware':'1.00','modes':['Positive Film','Negative Film'],'settings':'EXIF and MakerNote verified in gr4_official_metadata.json; sliders unknown',
        'maps':'unknown scene -> display sRGB JPEG; no paired DNG supplied','reference_frame':'display-referred examples only',
        'credibility':'official original output with exact mode; insufficient transform definition','gaps':['unrelated scenes between modes','no scene input or raw colour coordinates'],
        'license':'Ricoh/photographer copyright, private examination; original images outside repository','derived_file':'gr4_official_metadata.json'},
      'dpreview_gr4':{'url':'https://www.dpreview.com/samples/4901360886/ricoh-gr-iv-sample-gallery-street-photos/',
        'gallery_url':'https://www.dpreview.com/sample-galleries/5677004184/','exists':'已验证: article and gallery entry exist; original file access blocked',
        'camera':'GR IV','firmware':None,'maps':'potential RAW/JPEG originals, exact modes not verified','reference_frame':None,
        'credibility':'primary photographer samples if originals become accessible','raw_error':'HTTP 403; Performing security verification; Just a moment...',
        'gaps':['no original pair accepted or derived in this study'],'license':'private examination permitted, reproduction requires permission'},
      'rawpixls':{'url':'https://raw.pixls.us/json/getrepository.php','exists':'已验证: full JSON catalog downloaded; one GR IIIx record, no GR IV record',
        'record_id':5818,'camera':'GR IIIx','firmware':'1.02 verified from downloaded DNG','mode':'Monotone, DNGPrivateData 0x4f = 258',
        'maps':'DNG plus embedded 6000x4000 JPEG; not Positive, Negative or Hi-Contrast B&W',
        'reference_frame':'RAW -> rendered preview, preview is not a separately saved JPEG','credibility':'primary sample; useful after mode, preview processing and clipping checks',
        'gaps':['single scene, all sliders unknown','excluded from priority target fits because exact mode differs','catalog may add data later'],'license':'CC0 per individual sample record'},
      'colorreps_positive':{'url':'https://colorreps.com/lut/ricoh-gr-positive-film','artifact_url':'https://colorreps.com/luts/ricoh-positive.cube',
        'exists':'已验证: 33^3 cube and landing page','camera':'GR IV claimed by author, not independently verified','firmware':None,'mode':'Positive Film inspired',
        'maps':'assumed display sRGB -> display sRGB; normalized domain verified, encoding undocumented','reference_frame':'推断: display-referred',
        'credibility':'lowest; inspired title, no source pairs or reproducible fit evidence','gaps':['original GR IV pairs unavailable','settings and RAW conversion unspecified'],
        'license':'free download, redistribution license unspecified, original only in scratch','derived_file':'community_gr_probes.json'},
      'colorreps_negative':{'url':'https://colorreps.com/lut/ricoh-gr-negative-film','artifact_url':'https://colorreps.com/luts/ricoh-negative.cube',
        'exists':'已验证: 33^3 cube and landing page','camera':None,'firmware':None,'mode':'Negative Film inspired',
        'maps':'assumed display sRGB -> display sRGB; normalized domain verified, encoding undocumented','reference_frame':'推断: display-referred',
        'credibility':'lowest; model/generation unconfirmed','gaps':['cannot assign to III, IIIx or IV','no source pairs or sliders'],
        'license':'free download, redistribution license unspecified, original only in scratch','derived_file':'community_gr_probes.json'},
      'gr2013_official':{'url':'https://www.ricoh-imaging.co.jp/english/products/gr/spec/','exists':'已验证: official specs',
        'camera':'GR (2013)','firmware':None,'maps':None,'credibility':'mode existence only','reference_frame':None,'gaps':['no numerical transform obtained'],'license':'Ricoh website terms'},
      'gr2_official':{'url':'https://www.ricoh-imaging.co.jp/english/products/gr-2/spec/','exists':'已验证: official specs',
        'camera':'GR II','firmware':None,'maps':None,'credibility':'mode existence only','reference_frame':None,'gaps':['no numerical transform obtained'],'license':'Ricoh website terms'},
      'settings_context':{'url':'https://ricohcookbook.com/how-to/image-control-explained','exists':'已验证: public page',
        'maps':None,'reference_frame':None,'credibility':'settings context only; never a numeric golden','gaps':['recipe claims require independent camera/official verification'],'license':'website terms'},
      'isp_pipeline':{'path':'../isp_pipeline/REPORT.md','exists':'已验证: read in full when available','maps':'GXR static programmable-interface evidence only',
        'credibility':'static evidence, not camera response','reference_frame':None,'gaps':['type23 channel identities, type28 coordinates, actual order unverified'],'license':'local project research'},
      'gr_firmware_worker':{'path':'../gr_firmware/REPORT.md','exists':'已验证: report read in full; derived matrix JSON rehashed',
        'camera':['GR III','GR IIIx','GR IV'],'firmware':['2.10','1.60','1.11'],
        'maps':'mode-specific intermediate Q13 look matrices, shared base curves and MultiAxial components; complete RAW-to-JPEG function still incomplete',
        'reference_frame':'intermediate ISP domain; do not apply directly to sRGB or XYZ',
        'credibility':'highest provenance for fixed components, relies on upstream static extraction; firmware not independently read here',
        'gaps':['final curve generator, default sliders and gains','GR IV MultiAxial execution semantics','all golden validation still pending'],
        'license':'vendor firmware copyright; only derived numeric constraints referenced; no firmware redistribution',
        'derived_constraints_file':'gr_firmware_constraints.json'}
    }
    if dcp4['profiles']:
        refs['adobe_gr4_dcp']={'url':'https://helpx.adobe.com/camera-raw/desktop/dng-and-file-formats/adobe-dng-converter.html',
            'artifact_url':'https://download.adobe.com/pub/adobe/dng/mac/DNGConverter_17_5.pkg',
            'exists':'已验证: official package assembled from hashed prefixes and complete small HTTP ranges, expanded without installation; GR IV DCP data parsed',
            'camera':'Ricoh GR IV','firmware':None,'profile_version':'17.5 distribution',
            'maps':'matching GR IV linear RAW -> profile colorimetry/look/tone; sparse derived probes enter normalized XYZ D50 look stage',
            'reference_frame':'scene-referred camera input with display rendering stages',
            'credibility':'Adobe camera-matching numeric proxy, not original Ricoh firmware or validated GR IV JPEG rendering',
            'gaps':['No genuine GR IV RAW/JPEG pair acquired for validation','Exact firmware and camera sliders undocumented','Independent DCP interpreter is not ACR'],
            'license':'Adobe proprietary; only sparse derived numbers and hashes in repo; originals and EULA in scratch',
            'derived_file':'adobe_gr4_profiles.json','block_hash_file':'gr4_dcp_block_digests.json'}
    if (HERE/'gr4_hcwt_metadata.json').exists():
        refs['gr4_hcwt_raw']={'url':'https://havecamerawilltravel.com/ricoh-gr-iv-sample-images/',
            'artifact_url':'https://download.havecamerawilltravel.com/sample-images/ricoh-griv/Ricoh%20GR%20IV%20DNG-01.dng',
            'exists':'已验证: public DNG downloaded; model, metadata, matrices and preview read',
            'camera':'RICOH GR IV','firmware':None,'mode':'Standard, DNGPrivateData ImageTone=256',
            'software':'Adobe Photoshop Lightroom 14.5.1 Classic (Macintosh)',
            'maps':'DNG tags define a colorimetric model; no verified Ricoh camera JPEG output',
            'reference_frame':'RAW camera coordinates and Adobe-written profile metadata; not an accepted camera render pair',
            'credibility':'primary photographer file, but rewritten container and wrong priority mode',
            'gaps':['Original raw mosaic integrity not independently checked','Embedded preview not accepted as Ricoh JPEG','All sliders and original firmware unknown'],
            'license':'David Coleman copyright; RAW provided for compatibility testing; private examination only, originals outside repo',
            'derived_file':'gr4_hcwt_metadata.json','eligible_for_priority_fit':False}
        refs['pentaxforums_gr4_gallery']={'url':'https://www.pentaxforums.com/reviews/ricoh-gr-iv-camera-review/sample-photos.html',
            'exists':'已验证: primary contributor gallery with full-size JPEG links; no RAW links on this page',
            'camera':'GR IV','firmware':None,'maps':'unknown scene -> contributed JPEG; no paired RAW verified',
            'reference_frame':'display-referred samples','credibility':'output/context only, below official known-mode samples',
            'gaps':['mode/sliders and processing not verified','no numerical transform'],'license':'individual photographers retain copyright'}
    for sid in ['adobe_dcp','adobe_gr4_dcp']:
        if sid in refs:
            refs[sid]['native_mac_signature_authentication']='未通过: pkgutil reports invalid signature on both packages; cause unknown'
            refs[sid]['package_data_integrity']='All 9 archived XAR members match their directory digests; see package_integrity_audit.json. This is not signature authentication.'
    targets=[]
    for camera,code in [('GR (2013)','gr2013'),('GR II','gr2'),('GR III','gr3'),('GR IIIx','gr3x'),('GR IV','gr4')]:
        modes=['Positive Film','Standard','Hi-Contrast B&W']
        if code in ['gr3','gr3x','gr4']:modes.insert(1,'Negative Film')
        for mode in modes:
            suffix={'Positive Film':'positive','Negative Film':'negative','Standard':'standard','Hi-Contrast B&W':'hcbw'}[mode]
            ranked=[];derived=[]
            if code=='gr3' and suffix!='hcbw':
                ranked=[{'rank':1,'source_id':'bastibe_gr3','role':'observed RAW/JPEG numeric constraints'},
                        {'rank':2,'source_id':'adobe_dcp','role':'profile proxy; independent renderer error measured'}]
                derived=[{'file':'gr3_reference_measurements.json','key':'variants.'+suffix,'kind':'observed chart outputs + limited neutral interpolation'},
                         {'file':'adobe_gr_profiles.json','filter':{'camera_folder':'Ricoh GR III','profile_name':'Camera '+mode},'kind':'conditional canonical/chart/screen probes'}]
            elif code=='gr3x' and suffix!='hcbw':
                ranked=[{'rank':1,'source_id':'adobe_dcp','role':'model-specific numeric profiles, legacy/v2 kept separate'},
                        {'rank':2,'source_id':'rawpixls','role':'verified Monotone sample; excluded from this exact-mode fit'},
                        {'rank':3,'source_id':'bastibe_gr3','role':'other model, only after equivalence evidence; not a GR IIIx measurement'}]
                derived=[{'file':'adobe_gr_profiles.json','filter':{'camera_folder':'Ricoh GR IIIx','profile_name_contains':'Camera '+mode},'kind':'conditional canonical/chart/screen probes'}]
            elif code=='gr4':
                ranked=[{'rank':1,'source_id':'adobe_support_table','role':'newer-package matching-profile acquisition lead, not downloaded numeric data'},
                        {'rank':2,'source_id':'gr4_official','role':'known-mode output-only examples; no transform'},
                        {'rank':3,'source_id':'dpreview_gr4','role':'original-pair access blocked'}]
                if dcp4['profiles']:
                    if suffix!='hcbw':
                        ranked[0]={'rank':1,'source_id':'adobe_gr4_dcp','role':'model-specific numeric profile proxy; independent renderer unvalidated on GR IV'}
                        derived=[{'file':'adobe_gr4_profiles.json','filter':{'camera_folder':'Ricoh GR IV','profile_name_contains':'Camera '+mode},'kind':'conditional canonical/chart/screen probes'}]
                    else:ranked[0]={'rank':1,'source_id':'adobe_gr4_dcp','role':'verified seven-profile inventory lacks exact Hi-Contrast B&W; Hard Monotone is a separate mode'}
                if 'gr4_hcwt_raw' in refs:
                    ranked.append({'rank':len(ranked)+1,'source_id':'gr4_hcwt_raw','role':'downloaded GR IV DNG, rejected as exact-mode camera pair: Standard and Lightroom-written container'})
                if suffix in ['positive','negative']:
                    sid='colorreps_'+suffix
                    ranked.append({'rank':len(ranked)+1,'source_id':sid,'role':'conditional community proxy; not verified GR IV camera transform'})
                    derived.append({'file':'community_gr_probes.json','filter':{'mode':suffix},'kind':'low-credibility sRGB-assumption probes, not GR truth'})
            else:
                sid='gr2013_official' if code=='gr2013' else 'gr2_official' if code=='gr2' else 'adobe_dcp'
                ranked=[{'rank':1,'source_id':sid,'role':'mode/context only; no exact-mode numerical transform acquired'}]
            if code in ['gr3','gr3x','gr4'] and suffix!='hcbw':
                ranked=[{'rank':1,'source_id':'gr_firmware_worker','role':'official partial numeric constraints, not a complete target transform'}]+[{**r,'rank':r['rank']+1} for r in ranked]
            targets.append({'id':'ricoh_'+code+'_'+suffix,'camera':camera,'mode':mode,'priority':1 if suffix in ['positive','negative'] else 2,
                'ranked_sources':ranked,'derived_targets':derived or None,
                'derived_partial_constraints':'gr_firmware_constraints.json' if code in ['gr3','gr3x','gr4'] and suffix!='hcbw' else None,
                'golden_reference_function':None,'gxr_parameters':None,'gxr_best_case_residual_de00':None,
                'residual_status':'未知: no GXR screen control-response measurements, cannot infer achievable error from slider range',
                'deployable':False})
    deferred=[{'id':p['id'],'mode':p['official_mode'],'camera_family':p['reference_family'],'reason':'deferred by owner 2026-10-16; no chart targets derived'} for p in json.loads((ROOT/'research/color_targets/targets.json').read_text())['targets'] if not p['id'].startswith('ricoh_')]
    save('references.json',{'schema':'gr-first-numeric-reference-catalog-v2','as_of':'2026-10-16','scope_update_applied':True,
        'phase1_generations':['GR III/IIIx','GR IV'],'selection_rule':'owner selects the clean complete firmware reference available; never merge generations by shared mode name',
        'golden_reference_count':0,'targets':targets,'sources':refs,'deferred_other_brands':deferred,
        'negative_film_not_a_native_target_on':['GR (2013)','GR II'],
        'derived_data_semantics':'observed camera targets, profile proxies and community proxies remain distinct; nominal screen coordinates never treated as measured emitted colours'})
    receipts=[]
    for p in sorted(Path('/tmp/gxr_color_refs/downloads').glob('*/receipt.json')):
        r=json.loads(p.read_text())
        if r['status']=='downloaded':
            path=Path(r['local_path'])
            assert path.stat().st_size==r['bytes'] and sha(path)==r['sha256']
            r['re_fetch_instruction']='python3 -I research/color_references/fetch_source.py UNIQUE_NEW_NAME '+repr(r['url'])+' '+repr(Path(r['local_path']).name)
            if 'requested_byte_range' in r:r['re_fetch_instruction']+=' --byte-range '+':'.join(map(str,r['requested_byte_range']))
        receipts.append(r)
    profiles=[{k:p[k] for k in ['camera_folder','profile_name','path_scratch','bytes','sha256','copyright']} for p in dcp['profiles']+dcp4['profiles']]
    eula=Path('/tmp/gxr_color_refs/extracted/adobe16_5/Resources/en.txt')
    eula4=Path('/tmp/gxr_color_refs/extracted/adobe17_5/Resources/en.txt')
    assembly=Path('/tmp/gxr_color_refs/extracted/adobe175_download_assembly/assembly.json')
    save('source_manifest.json',{'schema':'source-and-download-manifest-v1','downloads':receipts,'extracted_adobe_profiles':profiles,
        'adobe_eula':{'path':str(eula),'bytes':eula.stat().st_size,'sha256':hashlib.sha256(eula.read_bytes()).hexdigest(),
            'terms_note':'Adobe proprietary license; license is not a grant to redistribute original profiles or tables'},
        'extraction_command':'pkgutil --expand-full /tmp/gxr_color_refs/downloads/adobe_converter_16_5/converter.pkg /tmp/gxr_color_refs/extracted/adobe16_5',
        'additional_extraction_commands':['pkgutil --expand-full /tmp/gxr_color_refs/extracted/adobe175_download_assembly/converter.pkg /tmp/gxr_color_refs/extracted/adobe17_5'] if dcp4['profiles'] else [],
        'additional_adobe_eulas':[{'path':str(eula4),'bytes':eula4.stat().st_size,'sha256':hashlib.sha256(eula4.read_bytes()).hexdigest(),'terms_note':'Adobe proprietary; no original redistribution'}] if eula4.exists() else [],
        'assembled_packages':[json.loads(assembly.read_text())] if assembly.exists() else [],
        'package_integrity_audit':'package_integrity_audit.json',
        'native_mac_signature_authenticated':False,'signature_failure_cause':None,
        'untrusted_code_executed':False,'installer_run':False,'vendor_originals_in_repo':False,
        'pre_scope_update_downloads':'Fujifilm package/docs acquired before owner narrowed scope; inert scratch only, no other-brand chart targets generated',
        'upstream_research_inputs':json.loads((HERE/'gr_firmware_constraints.json').read_text())['upstream_inputs']})
    print(json.dumps({'active_GR_targets':len(targets),'deferred_other_brand_looks':len(deferred),'download_receipts':len(receipts),'dcp_profiles':len(profiles)}))

if __name__=='__main__':main()
