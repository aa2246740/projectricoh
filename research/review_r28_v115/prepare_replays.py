"""Adapt the independent 114 review drivers; never invoke an input writer."""
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PRIOR = ROOT/'research/review_publish_v114'

def main():
    source = (PRIOR/'rebuild.py').read_text().replace('engine_v35_publish', 'engine_v36_r28').replace('full-r12', 'full-r13')
    (HERE/'rebuild.py').write_text(source)
    source = (PRIOR/'host_review.py').read_text()
    for old, new in [('engine_v35_publish','engine_v36_r28'), ('product-r12','product-r13'),
                     ('full-r12','full-r13'), ('verification.json','verification115.json'),
                     ('seed114','seed115')]:
        source = source.replace(old,new)
    source = source.replace("else:\n            v=load(CAND/'verify_v34c.py'", "elif row['generation']==114:old=CAND.parent/'local/reproduced114/GXRCE.DAT'\n        else:\n            v=load(CAND/'verify_v34c.py'")
    source = source.replace("if case in ('seed115','blackbox'):extra=", "if case in ('seed115','blackbox','sticky115'):extra=")
    source = source.replace("if row['generation']==113", "if row['generation']==113")
    source = source.replace("independent()\n", "independent()\n")
    source = source.replace("for unit in range(3):\n        text=run([OUT/'host','review'", "for unit in range(3):\n        text=run([OUT/'host','review'")
    (HERE/'host_review.py').write_text(source)
    source=(PRIOR/'extra_cases.inc.c').read_text()
    source=source.replace('if(unit==1||(i!=9&&i!=10))','if(i!=9&&i!=10)')
    source=source.replace('if(unit==1||(i<60||i>64))','if(i<60||i>64)')
    source=source.replace('        if(unit==1){CHECK(!f[1]&&RV_BYTE(0x2022f5ac)==7);continue;}\n','')
    source=source.replace('if(unit!=1){','{')
    source=source.replace('last_seed_only=1','first_seed_retained_tested_separately=1')
    # Additional exact 113->115 update, including cardless cold reboot.
    source=source.replace('    printf("REVIEW bounded_private_seed', '''    clean();put_file("/IROM/GXRCE0.DAT",old,old_bytes);
    put_file("/ATA1/GXRCE.DAT",new_raw,new_bytes);rename_refuse_existing=1;
    CHECK(rv_load(&root,&rv_trust)==RV_OK&&session()->selected_source==RV_SOURCE_CARD);
    memset(f,0,sizeof(f));flush_allowed=1;rv_hook_observe(&root,1,f);flush_allowed=0;
    CHECK(ig_host_install_status()==RV_OK&&session()->generation==115&&session()->rows==8);
    CHECK(file("/IROM/GXRCE0.DAT")&&!memcmp(file("/IROM/GXRCE0.DAT")->bytes,old,old_bytes));
    CHECK(file("/IROM/GXRCE1.DAT")&&!memcmp(file("/IROM/GXRCE1.DAT")->bytes,new_raw,new_bytes));
    CHECK(file("/ATA1/GXRCE.OK")&&!memcmp(file("/ATA1/GXRCE.OK")->bytes,new_raw,new_bytes));
    CHECK(!file("/ATA1/GXRCE.DAT"));file("/ATA1/GXRCE.OK")->exists=0;
    reboot();CHECK(rv_load(&root,&rv_trust)==RV_OK&&session()->generation==115&&session()->selected_source==RV_SOURCE_B);
    menu();CHECK(session()->rows==8);
    puts("REVIEW exact_113_to_115 old_preserved=1 OK_exact=1 cardless_IROM115=1");
    printf("REVIEW bounded_private_seed''')
    (HERE/'extra_cases.inc.c').write_text(source)
    (HERE/'native_flow.py').write_text((PRIOR/'native_flow.py').read_text())
    # This reader contains no mutations until main(), which this adapter never calls.
    (HERE/'artifact_review.py').write_text((PRIOR/'artifact_review.py').read_text())
    print('PASS review-owned drivers prepared')

if __name__=='__main__':main()
