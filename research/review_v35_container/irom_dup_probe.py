"""Keep product/resident C intact. Give native create real duplicate semantics."""
from pathlib import Path
import json
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import audit as a
h=a.HERE/'isolated/candidate';src=h/'host_v34c.c'
source=src.read_text()
needle='int32_t rv_native_create(const char *p,uint32_t f){mutation(p);return fixture_create(p,f);}'
assert source.count(needle)==1
source=source.replace(needle,r'''
static unsigned duplicate_irom_temp;
int32_t rv_native_create(const char *p,uint32_t f)
{
    unsigned i,fd;mutation(p);
    if(duplicate_irom_temp&&!strcmp(p,"/IROM/GXRCE.TMP")){
        /* Native FAT create scans for a free directory entry; it does not
         * truncate the first existing same-name entry (official 0x200b6d08). */
        for(i=0;i<64&&files[i].path[0];i++){}CHECK(i<64);
        for(fd=0;fd<2&&fds[fd].live;fd++){}CHECK(fd<2);
        strcpy(files[i].path,p);files[i].exists=1;files[i].length=0;
        fds[fd].live=1;fds[fd].file=i;fds[fd].write=1;fds[fd].pos=0;++opens;
        printf("IROM_NATIVE_CREATE new_entry=%u old_entry=%d\n",i,file_index(p,0));return fd+17;
    }
    return fixture_create(p,f);
}
''')
at=source.index('int main(int argc,char **argv)')
source=source[:at]+r'''
static void review_irom_duplicate(void)
{
    unsigned i,n=0;uint8_t oldtemp[4096];
    clean();memset(oldtemp,0x5a,sizeof(oldtemp));
    put_file("/IROM/GXRCE.TMP",oldtemp,sizeof(oldtemp));ready(1);
    native_fail_op=2;native_fail_path="/IROM/GXRCE.TMP";native_fail_left=3;
    duplicate_irom_temp=1;menu();duplicate_irom_temp=0;
    for(i=0;i<64;i++)if(files[i].exists&&!strcmp(files[i].path,"/IROM/GXRCE.TMP"))n++;
    CHECK(n==2&&native_fail_left==0&&ig_host_install_status()!=RV_OK);
    CHECK(!file("/IROM/GXRCE0.DAT")&&!file("/IROM/GXRCE1.DAT"));
    CHECK(!memcmp(file("/IROM/GXRCE.TMP")->bytes,oldtemp,sizeof(oldtemp)));
    CHECK(file("/ATA1/GXRCE.DAT")&&!file("/ATA1/GXRCE.OK"));
    printf("IROM_DUP count=%u install=%d rows=%u state=%u old_temp_preserved=1 new_verified_formal=0 DAT_remains=1\n",n,ig_host_install_status(),session()->rows,root.state);
}
'''+source[at:]
source=source.replace('if(!strcmp(argv[1],"seed115"))','if(!strcmp(argv[1],"irom-duplicate"))review_irom_duplicate();\n    else if(!strcmp(argv[1],"seed115"))',1)
probe=h/'host_v34c_irom.c';probe.write_text(source)
commands=[json.loads(x) for x in (h/'local/commands.jsonl').read_text().splitlines()]
cc=next(x['argv'] for x in reversed(commands) if x['label'].startswith('v34c-compile-') and str(src) in x['argv'])
ld=next(x['argv'] for x in reversed(commands) if x['label']=='v34c-link')
old=cc[cc.index('-o')+1];obj=a.HERE/'irom_dup.o';binary=a.HERE/'irom_dup'
a.run([str(probe) if x==str(src) else str(obj) if x==old else x for x in cc],'irom-dup-compile')
ld=[str(obj) if x==old else x for x in ld];ld[ld.index('-o')+1]=str(binary);a.run(ld,'irom-dup-link')
rows=[]
for unit in range(3):
 p=a.run([binary,'irom-duplicate',unit,h/'local/full-r13/GXRCE.DAT',h/'local/full-r13/trust.bin',h/'local/full-r13/effective-rows.bin',a.ROOT/'firmware/engine_v36_r28/candidate/local/full-r13/GXRCE.DAT','0'],f'irom-dup-unit-{unit}',check=False)
 rows.append(dict(unit=unit,returncode=p.returncode,stdout=p.stdout.decode(),stderr=p.stderr.decode()));print(p.stdout.decode(),p.stderr.decode(),flush=True)
a.dump('irom-duplicate-results.json',rows)
