"""Independent revision-bit parity in fresh, bounded processes."""
import json,os,subprocess,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from safety import enable,HERE,ROOT
enable()


def main():
    comparisons=[]
    for selected in ('','nand-word','preview-link','sd-long-response','nand-read-tail','nand-word,preview-link,sd-long-response,nand-read-tail'):
        pair={}
        for backend in ('native','reference'):
            name='switch-'+(selected.replace(',','-') or 'default')+'-'+backend+'-final11'
            argv=[sys.executable,'-I','-B',str(HERE/'scripts/limit.py'),'180',str(HERE/'scripts/native_corrections.py'),
                  '--backend',backend,'--fixes',selected,'--name',name]
            with (HERE/'runs'/(name+'.log')).open('w') as log:
                subprocess.run(argv,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=200)
            pair[backend]=json.loads((HERE/'runs'/(name+'.json')).read_text())
        fields=('sd_rows','nand_rows','nand_state','text_rows','text_final','preview','model_revision','full_states')
        assert all(pair['native'][key]==pair['reference'][key] for key in fields),selected
        comparisons.append(dict(fix=selected,passed=True,compared=list(fields)))
        print(json.dumps(comparisons[-1]),flush=True)
    result=dict(status='PASS',comparisons=comparisons,load=os.getloadavg())
    (HERE/'runs/model-switch-matrix-final11.json').write_text(json.dumps(result,indent=2)+'\n')


if __name__=='__main__':main()
