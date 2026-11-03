#!/usr/bin/env python3
"""Check inert XAR member digests and report native signature-tool results."""
import hashlib,json,struct,subprocess,zlib,xml.etree.ElementTree as ET
from pathlib import Path
HERE=Path(__file__).resolve().parent

def audit(path):
    header=path.open('rb').read(28)
    magic,hs,version,cl,ul,algorithm=struct.unpack('>4sHHQQI',header)
    assert magic==b'xar!' and cl<4*1024*1024 and ul<16*1024*1024
    with path.open('rb') as f:f.seek(hs);compressed=f.read(cl)
    root=ET.fromstring(zlib.decompress(compressed));heap=hs+cl
    results=[]
    def walk(node,prefix=''):
        for member in node.findall('file'):
            name=prefix+member.findtext('name')
            d=member.find('data')
            if d is not None:
                offset=int(d.findtext('offset'));length=int(d.findtext('length'))
                expected=d.findtext('archived-checksum');style=d.find('archived-checksum').attrib['style']
                assert heap+offset+length<=path.stat().st_size
                h=hashlib.new(style)
                with path.open('rb') as f:
                    f.seek(heap+offset);remaining=length
                    while remaining:
                        block=f.read(min(1024*1024,remaining));assert block
                        h.update(block);remaining-=len(block)
                results.append({'member':name,'bytes_archived':length,'algorithm':style,
                    'expected':expected,'actual':h.hexdigest(),'matches':h.hexdigest()==expected})
            walk(member,name+'/')
    walk(root.find('toc'))
    run=subprocess.run(['pkgutil','--check-signature',str(path)],capture_output=True,text=True,timeout=60)
    return {'path_scratch':str(path),'member_checks':results,'all_member_digests_match':all(x['matches'] for x in results),
        'native_signature_command':'pkgutil --check-signature '+str(path),'native_signature_exit_code':run.returncode,
        'native_signature_stdout':run.stdout,'native_signature_stderr':run.stderr,
        'digests_are_not_a_substitute_for_signature_authentication':True}

def main():
    items=[audit(Path(p)) for p in [
        '/tmp/gxr_color_refs/downloads/adobe_converter_16_5/converter.pkg',
        '/tmp/gxr_color_refs/extracted/adobe175_download_assembly/converter.pkg']]
    (HERE/'package_integrity_audit.json').write_text(json.dumps({'schema':'inert-pkg-integrity-v1','packages':items},indent=2)+'\n')
    print(json.dumps([{'path':i['path_scratch'],'members':len(i['member_checks']),'digests_match':i['all_member_digests_match'],
        'signature_exit':i['native_signature_exit_code'],'signature_stdout':i['native_signature_stdout']} for i in items]))
if __name__=='__main__':main()
