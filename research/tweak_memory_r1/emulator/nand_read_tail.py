"""Declare erased data after the selected page's data/spare stream is exhausted."""
PAGE_BYTES=2112


def install():
    import devices
    original=devices.NAND.read
    if getattr(original,'v310_read_tail',False):return
    def read(self,addr,n):
        if (0<=addr and addr+n<=4 and self.command in (0,0x30)
                and self.medium=='erased' and self.cursor+n>PAGE_BYTES):
            if self.busy:self.busy-=1
            page=self.pages.get(self.row,bytes([255])*PAGE_BYTES)
            prefix=page[self.cursor:min(self.cursor+n,PAGE_BYTES)] if self.cursor<PAGE_BYTES else b''
            self.cursor+=n;self.reads+=n
            return prefix+bytes([255])*(n-len(prefix))
        return original(self,addr,n)
    read.v310_read_tail=True
    devices.NAND.read=read
