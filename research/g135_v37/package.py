"""Assemble the thirty-file g135 package: v3.7 body, 28 fixed official files, new DAT."""
from pathlib import Path
import hashlib
import json
import shutil
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from fences import ROOT,WORK,ENGINE,PACKAGE,enable,check_inputs

BODY_SHA='d00607405a5bd33290f99e9eda20df31a46386b6e0891cd5e62b15a9e3376283'

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    enable();check_inputs()
    target=PACKAGE/'local/SD_ROOT';target.mkdir(parents=True,exist_ok=True)
    (PACKAGE/'.gitignore').write_text('local/\n')
    if not (PACKAGE/'SD_ROOT').exists():(PACKAGE/'SD_ROOT').symlink_to('local/SD_ROOT',target_is_directory=True)
    source=ROOT/'firmware/package_v37_redisplay/SD_ROOT';official=ROOT/'firmware/package_v36_g120b/SD_ROOT'
    records=[]
    for p in sorted(source.iterdir()):
        if p.name=='GXRCE.DAT':continue
        assert p.is_file();shutil.copyfile(p,target/p.name)
        assert sha(p)==sha(target/p.name)
        if p.name=='ilaunch3':assert sha(p)==BODY_SHA
        else:assert sha(p)==sha(official/p.name),p.name
        records.append({'name':p.name,'bytes':p.stat().st_size,'sha256':sha(p)})
    assert len(records)==29
    dat=ENGINE/'candidate/local/full-r13/GXRCE.DAT';shutil.copyfile(dat,target/'GXRCE.DAT')
    assert len(list(target.iterdir()))==30
    (PACKAGE/'CARD_SHA256SUMS').write_text(''.join(f'{sha(p)}  {p.name}\n' for p in sorted(target.iterdir())))
    result={'files':30,'fixed_files_equal_gen120b':28,'body':'package_v37_redisplay/ilaunch3','body_sha256':BODY_SHA,
            'dat_bytes':dat.stat().st_size,'generation':int.from_bytes(dat.read_bytes()[28:32],'big'),
            'dat_sha256':sha(dat),'fixed_files':records}
    (WORK/'package.json').write_text(json.dumps(result,indent=2)+'\n')
    check_inputs();print(json.dumps({k:v for k,v in result.items() if k!='fixed_files'}))

if __name__=='__main__':main()
