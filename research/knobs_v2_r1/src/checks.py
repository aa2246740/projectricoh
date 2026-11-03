"""Byte, hardware-envelope, curve and steady-state RPC accounting checks."""
import struct
import zlib
import math
import support as s
s.dependencies()
import numpy as np
import knobs as k


def curves(b):
    yield 'B5',20,82
    yield 'B14',456,518
    if b[1]&16:yield 'B20',284,346
    if b[1]&4:
        yield 'C',20,379
        yield 'D',20,412


def inspect(b,dense=False):
    errors=[];limits=[];curve_stats=[]
    for name,at,out in curves(b):
        xs=np.array([0,*struct.unpack_from('>31H',b,at),4095],dtype=np.int64)
        ys=np.array(list(b[out:out+33]),dtype=np.int64)
        dx=np.diff(xs);dy=np.diff(ys)
        if np.any(dx[:31]<=0) or np.any(dx<0) or xs[-2]>4095:errors.append(name+': invalid input nodes')
        if np.any(dy<0):errors.append(name+': nonmonotone')
        if np.any((dx==0)&(dy!=0)):errors.append(name+': unequal outputs on duplicate endpoint')
        keep=dx>0
        bound=int(np.max((dy[keep]+dx[keep]-1)//dx[keep]))
        if bound>1:errors.append(name+': skips 8-bit codes on a unit 12-bit input ramp')
        q=dict(row=name,max_node_jump=int(dy.max()),max_12bit_lsb_jump_bound=bound,
               zero_slope_segments=int((dy==0).sum()))
        if dense:
            xx=np.arange(4096,dtype=np.int64);j=np.searchsorted(xs,xx,side='right')-1;j=np.clip(j,0,31)
            den=xs[j+1]-xs[j];den=np.maximum(den,1)
            yy=ys[j]+((xx-xs[j])*(ys[j+1]-ys[j])+den//2)//den
            yy[-1]=ys[-1]
            q['max_12bit_lsb_jump_exact']=int(np.diff(yy).max())
            q['distinct_output_codes']=len(np.unique(yy))
            if np.any(np.diff(yy)<0):errors.append(name+': nonmonotone dense ramp')
        curve_stats.append(q)
    for sector in range(24):
        raw=b[115+sector*4:119+sector*4];v=[k.dec(z,128) for z in raw]
        if sector not in (0,11,17,23) and (v[0]!=v[3] or v[1]!=-v[2]):errors.append(f'unsupported asymmetric sector {sector}')
        for j,z in enumerate(v):
            if abs(z)==127:limits.append(dict(row='colour',index=sector*4+j,value=z,limit=127))
    raw=struct.unpack_from('>28H',b,216);w=k.words(b)
    for i,(r,v) in enumerate(zip(raw,w)):
        if r&~4095:errors.append(f'matrix high bits {i}')
        if i%14<9:
            lim=2047 if i%14<3 else 1279
            if abs(v)>lim:errors.append(f'matrix overflow {i}')
            if abs(v)==lim:limits.append(dict(row='matrix',index=i,value=v,limit=lim))
        elif i%14 in (10,11):
            if not 120<=r<=136:errors.append(f'offset outside current validator {i}')
            if r in (120,136):limits.append(dict(row='matrix_offset',index=i,value=r,limit='120..136'))
        elif r:errors.append(f'matrix reserved tail {i}')
    for at,n,crc in k.CRCS:
        if zlib.crc32(b[at:at+n])!=s.u32(b,crc):errors.append(f'CRC {at}')
    if bool(b[1]&4)!=bool(b[1]&2) or s.u16(b,445)!=(0 if b[1]&4 else 2):errors.append('T/flags mismatch')
    return dict(errors=errors,limits=limits,curves=curve_stats,
                max_12bit_lsb_jump_bound=max(x['max_12bit_lsb_jump_bound'] for x in curve_stats),
                max_node_jump=max(x['max_node_jump'] for x in curve_stats),
                Y_sums=[sum(w[:3]),sum(w[14:17])])


def changed(before,after):
    rows=[]
    for name,at,n,crc in s.ROW_SPECS:
        count=sum(a!=b for a,b in zip(before[at:at+n],after[at:at+n]))
        if count:rows.append(dict(row=name,bytes=n,changed_bytes=count))
    return dict(rows=rows,changed_row_bytes=sum(x['changed_bytes'] for x in rows),
                changed_entry_bytes=sum(a!=b for a,b in zip(before,after)),
                flags_changed=before[1]!=after[1],T_changed=before[445:447]!=after[445:447])


def rpc(before,after,addresses):
    changes=changed(before,after);have=bool(before[1]&4);want=bool(after[1]&4)
    if not changes['rows'] and have==want:return dict(rpc8=0,W=0,XV=0,begin_end=0,epoch_calls=0)
    xv=2;writes=0
    if have:xv+=1;writes+=1
    if any(r['row']=='B5' for r in changes['rows']):xv+=2
    for r in changes['rows']:
        i=next(i for i,q in enumerate(s.ROW_SPECS) if q[0]==r['row'])
        xv+=2;writes+=(r['bytes']+(addresses[i]&1)+1)//2
    if want:xv+=3;writes+=1
    total=xv+writes+2
    return dict(rpc8=total,W=writes,XV=xv,begin_end=2,epoch_calls=2*total-2)


def level_request(group,level):
    if group['param']=='amount':return k.Request(level)
    return k.request_for(group['param'],group['doses'][str(level)],
                         wb_method=group.get('wb_method',0),tone_method=group.get('tone_method',0))
