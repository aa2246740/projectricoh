"""Per-process full CPU-store tapes, including stores skipped by native filters."""
import hashlib,os,struct
from pathlib import Path
from common import sha
WRITER=struct.Struct('>5I')
class WriteTape:
    default_case="parent"
    def __init__(self,root,index):
        self.root,self.index=Path(root),index;self.stream=None;self.case=type(self).default_case;self.records=0;self.bytes=0;self.digest=hashlib.sha256()
    def prepare_fork(self):
        if self.stream:self.stream.flush()
    def after_fork(self,index):
        if self.stream:self.stream.close()
        self.stream=None;self.case='child-%03d'%index;self.records=self.bytes=0;self.digest=hashlib.sha256()
    def __call__(self,backend,before):raise AssertionError('CPU instruction tape is disabled')
    def write(self,address,value,width,pc,origin):
        data=(value&((1<<(8*width))-1)).to_bytes(width,'big')
        self.event(address,data,pc,origin)
    def event(self,address,data,pc,origin):
        if self.stream is None:
            self.path=self.root/('%s-backend-%03d.bin'%(self.case,self.index));self.path.parent.mkdir(parents=True,exist_ok=True);self.stream=self.path.open('wb',buffering=1048576)
        text=origin.encode();row=WRITER.pack(address,len(data),pc,len(text),len(data))+text+data
        self.stream.write(row);self.digest.update(row);self.records+=1;self.bytes+=len(row)
    def close(self):
        if self.stream is None:return None
        self.stream.close();self.stream=None;actual=sha(self.path)
        if actual!=self.digest.hexdigest():raise AssertionError('write tape readback differs')
        return {'name':self.path.name,'records':self.records,'bytes':self.bytes,'sha256':actual}
