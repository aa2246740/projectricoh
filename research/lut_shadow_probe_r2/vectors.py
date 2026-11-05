"""Independent barycentric oracle and deliberately non-photographic private cases."""
import itertools
import random
import struct

def coordinates():
    result=[]
    for value in range(256):
        cell,fraction=divmod(value*16*256//255,256)
        if value==255: cell,fraction=15,256
        result.append((cell<<16)|fraction)
    return result

def table(kind):
    nodes=[]
    for v in range(17):
        for u in range(17):
            for y in range(17):
                if kind=='identity': values=[component*4080 for component in (y,u,v)]
                elif kind=='extreme': values=[65535*((y+u+v+channel)&1) for channel in range(3)]
                else: values=[(y*4051+u*2017+v*997+(y*u+u*v+v*y)*127+c*21701)&65535 for c in range(3)]
                nodes.extend(values)
    return nodes

def pixel(values,nodes,coord):
    packed=[coord[x] for x in values]
    position=[p>>16 for p in packed]; fractions=[p&65535 for p in packed]
    order=sorted(range(3),key=lambda axis:(-fractions[axis],axis))
    f=[fractions[i] for i in order]
    weights=[256-f[0],f[0]-f[1],f[1]-f[2],f[2]]
    corners=[position.copy()]
    for axis in order:
        position[axis]+=1; corners.append(position.copy())
    return [sum(w*nodes[((p[2]*17+p[1])*17+p[0])*3+c] for w,p in zip(weights,corners)) for c in range(3)]

def transform(word,nodes,coord):
    y0,y1,u,v=word.to_bytes(4,'big')
    a=pixel((y0,u,v),nodes,coord); b=pixel((y1,u,v),nodes,coord)
    values=((a[0]+32768)>>16,(b[0]+32768)>>16,
            (a[1]+b[1]+65536)>>17,(a[2]+b[2]+65536)>>17)
    return bytes(min(255,x) for x in values)

def words():
    result=[0,0xffffffff,0x00ff00ff,0xff00ff00,0x80808080,0x00ff8080,0xff008080]
    for a,b,c in itertools.permutations((23,87,151)):
        result.append((a<<24)|((255-a)<<16)|(b<<8)|c)
    for a,b,c in itertools.product((0,1,15,16,127,128,239,240,254,255),repeat=3):
        result.append((a<<24)|((255-a)<<16)|(b<<8)|c)
    result.extend((x<<24)|(x<<16)|(128<<8)|128 for x in range(256))
    randomizer=random.Random(169)
    result.extend(randomizer.getrandbits(32) for _ in range(512))
    return result

def packed(values): return struct.pack('>'+str(len(values))+'H',*values)
