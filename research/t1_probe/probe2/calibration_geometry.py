import numpy as np, math
from scipy import ndimage

def locate(a,rgb,lay,seed_H=None):
    g=a.gray_of(rgb);hh,ww=g.shape
    cs,size=a.marker_candidates(g)
    if seed_H is not None:
        found=[a.refine_marker(g,a.apply_h(seed_H,lay['markers'][k]['center_px']),size) for k in a.ORDER]
        if any(r is None for r in found):raise ValueError('04-seeded marker refinement failed')
        TL,TR,BR,BL=found
    else:
        rs=[a.refine_marker(g,c['xy'],size) for c in cs];rs=[r for r in rs if r is not None]
        TL=min((r for r in rs if r['xy'][0]<ww*.3 and r['xy'][1]<hh*.3),key=lambda r:r['xy'][0])
        TR=max((r for r in rs if r['xy'][0]>ww*.7 and r['xy'][1]<hh*.3),key=lambda r:r['xy'][0])
        BR=max((r for r in rs if r['xy'][0]>ww*.7 and r['xy'][1]>hh*.7),key=lambda r:r['xy'][0])
        BL=a.refine_marker(g,np.array(TL['xy'])+np.array(BR['xy'])-np.array(TR['xy']),size)
    mk=lay['markers'];src=np.array([mk[k]['center_px'] for k in a.ORDER]);dst=np.array([r['xy'] for r in (TL,TR,BR,BL)])
    H=a.dlt(src,dst)
    source=[];measured=[];residuals=[];linesall={}
    # Collect many outer-border edge samples across all four corner markers.
    for k in a.ORDER:
        x0,y0,x1,y1=mk[k]['bbox_px'];lines={}
        for axis in (0,1):
            for side in (0,1):
                edge=(x0,x1)[side] if axis==0 else (y0,y1)[side]
                tangent=np.linspace((y0 if axis==0 else x0)+35,(y1 if axis==0 else x1)-35,31)
                screen=np.zeros((31,2));screen[:,axis]=edge;screen[:,1-axis]=tangent
                center=a.apply_h(H,screen)
                J=a.local_jacobian(H,*mk[k]['center_px']);normal=J[:,axis]/np.linalg.norm(J[:,axis])
                offsets=np.linspace(-16,16,129)
                pts=center[:,None,:]+offsets[None,:,None]*normal
                vals=a.sample_bilinear(g,pts);smooth=ndimage.gaussian_filter1d(vals,1.5,axis=1)
                deriv=np.gradient(smooth,offsets,axis=1)*(1 if side==0 else -1)
                pos=np.argmax(deriv,axis=1)
                keep=(pos>2)&(pos<126)
                s=screen[keep];loc=[]
                for c,j,dd in zip(center[keep],pos[keep],deriv[keep]):
                    den=dd[j-1]-2*dd[j]+dd[j+1]
                    delta=0 if den==0 else .5*(dd[j-1]-dd[j+1])/den
                    loc.append(c+(offsets[j]+.25*delta)*normal)
                loc=np.array(loc)
                # Fit the physical edge as a straight line and keep only consistent edge positions.
                independent=loc[:,1-axis];dependent=loc[:,axis]
                ok=np.ones(len(loc),bool)
                for _ in range(3):
                    co=np.polyfit(independent[ok],dependent[ok],1);err=dependent-np.polyval(co,independent);ok=np.abs(err-np.median(err))<max(.6,3*np.median(np.abs(err-np.median(err))))
                source.extend(s[ok]);measured.extend(loc[ok]);residuals.extend(err[ok]);lines[f'{axis}_{side}']={'n':int(ok.sum()),'rms':float(np.sqrt(np.mean(err[ok]**2)))}
        linesall[k]=lines
    source=np.array(source);measured=np.array(measured)
    # Border samples constrain line distance, not their tangent parameter. Iterate correspondence by projection.
    H=a.dlt(source,measured)
    for _ in range(5):
        pred=a.apply_h(H,source);adjusted=measured.copy()
        cursor=0
        for k in a.ORDER:
            for axis in (0,1):
                for side in (0,1):
                    n=linesall[k][f'{axis}_{side}']['n'];s=slice(cursor,cursor+n);loc=measured[s]
                    co=np.polyfit(loc[:,1-axis],loc[:,axis],1)
                    p=pred[s];v=np.zeros_like(p);v[:,axis]=1;v[:,1-axis]=-co[0];norm=np.linalg.norm(v,axis=1)
                    signed=(p[:,axis]-co[0]*p[:,1-axis]-co[1])/norm
                    adjusted[s]=p-signed[:,None]*v/norm[:,None];cursor+=n
        H=a.dlt(source,adjusted)
    rr=np.linalg.norm(a.apply_h(H,source)-adjusted,axis=1)
    corr={k:{n:a.checker_corr(g,H,mk[k],n) for n in (3,4,6,8)} for k in a.ORDER};counts={k:max(corr[k],key=corr[k].get) for k in a.ORDER};score=sum(corr[k][mk[k]['n_cells']] for k in a.ORDER)
    if any(counts[k]!=mk[k]['n_cells'] for k in a.ORDER):raise ValueError(f'border checker mismatch {counts}')
    S=[];D=[]
    for k in a.ORDER:
        for uv in mk[k]['inner_corners_px']:
            v=a.saddle_refine(g,a.apply_h(H,uv),a.local_jacobian(H,*uv),mk[k]['cell_px'])
            if v is not None:S.append(uv);D.append(v[0])
    er=np.linalg.norm(a.apply_h(H,S)-D,axis=1)
    J=a.local_jacobian(H,1728,1117)
    return {'H':H,'Hinv':np.linalg.inv(H),'marker_score':score,'marker_cells':counts,'marker_corr':corr,'mirrored':False,'corners_used':len(S),'corners_found':len(S),'corner_rms_px':float(np.sqrt(np.mean(er**2))),'rotation_deg':math.degrees(math.atan2(J[1,0],J[0,0])),'scale':float(math.sqrt(abs(np.linalg.det(J)))),'marker_centres_img':{k:a.apply_h(H,mk[k]['center_px']).tolist() for k in a.ORDER},'border_normal_fit_rms_px':float(np.sqrt(np.mean(rr**2))),'border_line_residual_rms_px':float(np.sqrt(np.mean(np.array(residuals)**2))),'border_lines':linesall,'locator':'white outer edges of four markers; inner checker corners independently checked, not used in H fit'}

def install(a):a.locate_screen=lambda rgb,lay:locate(a,rgb,lay)
