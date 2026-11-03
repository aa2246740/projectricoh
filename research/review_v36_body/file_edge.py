"""In-memory device file boundary for real gen 116 storage instructions.

No SD/IROM device is accessed. The original native bridge ABI is r4..r6.
"""
import hashlib

class Files:
    def __init__(self, h, product, contents=None):
        self.h,self.product=h,product
        # Use the identical in-memory header rebind as the other v3.6 body runs.
        # The source gen116 DAT and every payload byte remain unchanged.
        assert product.files.dat[256:]==product.dat[256:]
        self.contents=contents if contents is not None else {"/IROM/GXRCE0.DAT":bytes(product.files.dat)}
        self.fds={};self.next=3;self.log=[]
        from product_execute import cstr
        path=lambda b,reg="r4":cstr(h,b.get_reg(reg))
        handlers={
            0x200a40b4:("review_open",lambda b:self.open(path(b),b.get_reg("r5"))),
            0x200a449c:("review_read",lambda b:self.read(b.get_reg("r4"),b.get_reg("r5"),b.get_reg("r6"))),
            0x200a437c:("review_close",lambda b:self.close(b.get_reg("r4"))),
            0x200a544c:("review_create",lambda b:self.create(path(b),b.get_reg("r5"))),
            0x200a45e8:("review_write",lambda b:self.write(b.get_reg("r4"),b.get_reg("r5"),b.get_reg("r6"))),
            0x200a49d8:("review_rename",lambda b:self.rename(path(b),path(b,"r5"))),
            0x200a4910:("review_delete",lambda b:self.delete(path(b))),
        }
        for addr,(name,fn) in handlers.items():
            h.b.breakpoints.pop(addr,None)
            product._native(addr,name,fn)
    def fd(self,path,write):
        fd=self.next;self.next+=1;self.fds[fd]=[path,0,write];return fd
    def open(self,path,flags):
        self.log.append(dict(op="open",path=path,flags=flags))
        assert flags in (0,2)
        return self.fd(path,flags==2) if path in self.contents else -1
    def create(self,path,flags):
        self.log.append(dict(op="create",path=path,flags=flags))
        assert flags==2
        self.contents[path]=b""
        return self.fd(path,True)
    def read(self,fd,buf,n):
        if fd not in self.fds:return -1
        path,pos,write=self.fds[fd];assert not write
        data=self.contents[path][pos:pos+n]
        if data and buf:self.h.b.write(buf,data)
        self.fds[fd][1]+=len(data)
        self.log.append(dict(op="read",path=path,offset=pos,n=n,result=len(data)))
        return len(data)
    def write(self,fd,buf,n):
        if fd not in self.fds:return -1
        path,pos,write=self.fds[fd];assert write
        data=self.h.b.read(buf,n)
        old=self.contents[path]
        self.contents[path]=old[:pos]+data+old[pos+n:]
        self.fds[fd][1]+=n
        self.log.append(dict(op="write",path=path,offset=pos,n=n,sha256=hashlib.sha256(data).hexdigest()))
        return n
    def close(self,fd):
        self.log.append(dict(op="close",fd=fd))
        return 0 if self.fds.pop(fd,None) is not None else -1
    def rename(self,src,dst):
        self.log.append(dict(op="rename",src=src,dst=dst))
        if src not in self.contents or dst in self.contents:return -1
        self.contents[dst]=self.contents.pop(src)
        return 0
    def delete(self,path):
        self.log.append(dict(op="delete",path=path))
        if path not in self.contents:return -1
        del self.contents[path];return 0

