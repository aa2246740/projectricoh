"""Independent barycentric reference and deterministic full-table fixtures."""
import itertools
import struct
import zlib

COUNTS = (4096,4,64,512)
SPECIAL = [0x00000000,0xffffffff,0x00ff00ff,0xff00ff00]
for a,b,c in itertools.permutations((23,87,151)):
    SPECIAL.append((a<<24)|((255-a)<<16)|(b<<8)|c)
SPECIAL += [0x80808080,0x00ff8080,0xff008080,0x01010101,0xfefefefe,0x0000ffff]


def input_word(i):
    if i<len(SPECIAL): return SPECIAL[i]
    if i<128:
        y=(i>>3)&255
        return (y<<24)|(y<<16)|(128<<8)|128
    x=(i*0x9e3779b9+0x7f4a7c15)&0xffffffff
    x^=x>>16;x=(x*0x85ebca6b)&0xffffffff;x^=x>>13
    return x


def coordinates(n=17):
    result=[]
    for v in range(256):
        q=v*(n-1)*256//255
        cell,frac=divmod(q,256)
        if v==255:cell,frac=n-2,256
        result.append((cell<<16)|frac)
    return result


def table(kind='mixed',n=17):
    result=[]
    for c3 in range(n):
        for c2 in range(n):
            for y in range(n):
                if kind=='identity':values=[y*65280//(n-1),c2*65280//(n-1),c3*65280//(n-1)]
                elif kind=='extremes':values=[65535*((y+c2+c3+k)&1) for k in range(3)]
                else:
                    # Full u16 domain, non-separable and deliberately non-photographic.
                    values=[(y*4051+c2*2017+c3*997+(y*c2+c2*c3+c3*y)*127+k*21701)&65535 for k in range(3)]
                    if y==c2==c3==0:values=[0,65535,0]
                    if y==c2==c3==n-1:values=[65535,0,65535]
                result+=values
    return result


def pixel(y,c2,c3,nodes,coord,n=17):
    packed=[coord[y],coord[c2],coord[c3]]
    cell=[x>>16 for x in packed];fractions=[x&65535 for x in packed]
    order=sorted(range(3),key=lambda a:(-fractions[a],a))
    f=[fractions[a] for a in order]
    weights=[256-f[0],f[0]-f[1],f[1]-f[2],f[2]]
    verts=[tuple(cell)]
    for a in order:cell[a]+=1;verts.append(tuple(cell))
    return [sum(w*nodes[((v[2]*n+v[1])*n+v[0])*3+c] for w,v in zip(weights,verts)) for c in range(3)]


def transform(word,nodes,coord,n=17):
    y0,y1,c2,c3=word.to_bytes(4,'big')
    a=pixel(y0,c2,c3,nodes,coord,n);b=pixel(y1,c2,c3,nodes,coord,n)
    return bytes((min(255,(a[0]+32768)>>16),min(255,(b[0]+32768)>>16),
                  min(255,(a[1]+b[1]+65536)>>17),min(255,(a[2]+b[2]+65536)>>17)))


def generated():
    nodes=table();coord=coordinates();data=[input_word(i) for i in range(4096)]
    output=b''.join(transform(w,nodes,coord) for w in data)
    crcs=[zlib.crc32(output[:n*4]) for n in COUNTS]
    input_crcs=[zlib.crc32(b''.join(struct.pack('>I',w) for w in data[:n])) for n in COUNTS]
    code='#include "kernel.h"\nconst uint16_t p0_table[P0_NODES*3]={\n'+','.join(str(x) for x in nodes)+'};\n'
    code+='const uint32_t p0_coord[256]={'+','.join(str(x)+'u' for x in coord)+'};\n'
    code+='const uint32_t p0_expected_crc[4]={'+','.join(str(x)+'u' for x in crcs)+'};\n'
    code+='const uint32_t p0_input_crc[4]={'+','.join(str(x)+'u' for x in input_crcs)+'};\n'
    code+='uint32_t p0_input(uint32_t i){ static const uint32_t s[]={'+','.join(hex(x)+'u' for x in SPECIAL)+'};uint32_t x;\n'
    code+='if(i<sizeof(s)/sizeof(s[0])){return s[i];}\nif(i<128){x=(i>>3)&255u;return (x<<24)|(x<<16)|(128u<<8)|128u;}\n'
    code+='x=i*0x9e3779b9u+0x7f4a7c15u;x^=x>>16;x*=0x85ebca6bu;x^=x>>13;return x;}\n'
    return code,nodes,coord,crcs,input_crcs
