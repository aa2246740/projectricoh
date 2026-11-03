"""Restricted, original decoder for this GR III DNG's SOF3 predictor-1 scan.

Not a general RAW library. Unsupported files fail explicitly. It does not run
downloaded code. JPEG syntax follows ITU-T T.81 lossless sequential DPCM.
"""
import numpy as np

def decode(data):
    if data[:2]!=b'\xff\xd8':raise ValueError('Missing SOI')
    p=2; tables={}; frame=None; scan=None
    while p<len(data):
        if data[p]!=255:raise ValueError('Marker alignment')
        m=data[p+1]; n=int.from_bytes(data[p+2:p+4],'big');b=data[p+4:p+2+n];p+=2+n
        if m==0xc3:
            precision=b[0]; h=int.from_bytes(b[1:3],'big');w=int.from_bytes(b[3:5],'big');nc=b[5]
            if len(b)!=6+nc*3 or any(b[7+3*i]!=0x11 for i in range(nc)):raise ValueError('Sampling')
            frame=(precision,h,w,nc)
        elif m==0xc4:
            k=0
            while k<len(b):
                ident=b[k]; counts=b[k+1:k+17]; k+=17; values=b[k:k+sum(counts)];k+=sum(counts)
                if ident>>4:raise ValueError('AC table in lossless scan')
                lengths=np.zeros(65536,np.uint8); syms=np.zeros(65536,np.uint8); code=0;j=0
                for size,count in enumerate(counts,1):
                    for _ in range(count):
                        a=code<<(16-size); z=(code+1)<<(16-size)
                        lengths[a:z]=size;syms[a:z]=values[j];j+=1;code+=1
                    code<<=1
                tables[ident&15]=(lengths,syms)
        elif m==0xdd:raise ValueError('Restart intervals unsupported')
        elif m==0xda:
            nc=b[0];ids=[b[2+2*i]>>4 for i in range(nc)]
            if b[1+2*nc]!=1 or b[2+2*nc]!=0 or b[3+2*nc]!=0:raise ValueError('Only predictor 1, Pt=0')
            scan=ids;break
    if frame is None or scan is None:raise ValueError('Missing frame/scan')
    precision,h,w,nc=frame
    if len(scan)!=nc or len(set(scan))!=1:raise ValueError('Only one shared DC table')
    entropy=data[p:]
    if not entropy.endswith(b'\xff\xd9'):raise ValueError('Missing EOI')
    entropy=entropy[:-2]
    stripped=entropy.replace(b'\xff\x00',b'')
    if b'\xff' in stripped:raise ValueError('Unexpected entropy marker')
    entropy=entropy.replace(b'\xff\x00',b'\xff')+b'\0\0\0\0'
    lengths,syms=tables[scan[0]]
    differences=np.empty(h*w*nc,np.int32)
    pos=0;buf=0;bits=0
    for i in range(len(differences)):
        while bits<16:
            buf=(buf<<8)|entropy[pos];pos+=1;bits+=8
        prefix=(buf>>(bits-16))&65535;length=int(lengths[prefix]);s=int(syms[prefix])
        if length==0:raise ValueError('Invalid Huffman prefix')
        bits-=length
        if s==0: d=0
        elif s==16:d=-32768
        else:
            while bits<s:
                buf=(buf<<8)|entropy[pos];pos+=1;bits+=8
            bits-=s;d=(buf>>bits)&((1<<s)-1)
            if d<(1<<(s-1)):d-=((1<<s)-1)
        buf&=(1<<bits)-1
        differences[i]=d
    differences=differences.reshape(h,w,nc)
    first=(1<<(precision-1))+np.cumsum(differences[:,0,:],axis=0,dtype=np.int64)
    raw=np.cumsum(differences,axis=1,dtype=np.int64)+(first-differences[:,0,:])[:,None,:]
    raw&=(1<<precision)-1
    return raw.reshape(h,w*nc).astype(np.uint16),{'precision':precision,'sof_wh':[w,h],
        'components':nc,'predictor':1,'point_transform':0,'restart_interval':0,
        'decoder':'original restricted Python SOF3; no independent pixel decoder confirmation'}
