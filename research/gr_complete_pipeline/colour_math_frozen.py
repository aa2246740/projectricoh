"""Small colour-math implementation for this study, column-vector matrices."""
import numpy as np

D50 = np.array([0.96422, 1., 0.82521])
D65 = np.array([0.95047, 1., 1.08883])
SRGB_XYZ = np.array([[.4124564,.3575761,.1804375],
                     [.2126729,.7151522,.0721750],
                     [.0193339,.1191920,.9503041]])
BRADFORD = np.array([[.8951,.2664,-.1614],[-.7502,1.7135,.0367],[.0389,-.0685,1.0296]])

def cat(src, dst):
    return np.linalg.inv(BRADFORD) @ np.diag((BRADFORD@dst)/(BRADFORD@src)) @ BRADFORD

def srgb_decode(rgb):
    rgb=np.asarray(rgb,dtype=float)
    return np.where(rgb <= .04045, rgb/12.92, ((np.maximum(rgb,0)+.055)/1.055)**2.4)

def srgb_encode(rgb):
    rgb=np.asarray(rgb,dtype=float)
    return np.where(rgb <= .0031308, 12.92*rgb, 1.055*np.maximum(rgb,0)**(1/2.4)-.055)

def xyz_lab(xyz, white=D50):
    t=np.asarray(xyz)/white
    f=np.where(t>(6/29)**3,np.cbrt(t),t/(3*(6/29)**2)+4/29)
    return np.stack([116*f[...,1]-16,500*(f[...,0]-f[...,1]),200*(f[...,1]-f[...,2])],axis=-1)

def lab_xyz(lab, white=D50):
    lab=np.asarray(lab)
    fy=(lab[...,0]+16)/116
    f=np.stack([fy+lab[...,1]/500,fy,fy-lab[...,2]/200],axis=-1)
    t=np.where(f>6/29,f**3,3*(6/29)**2*(f-4/29))
    return t*white

def rgb_lab(rgb):
    xyz=srgb_decode(rgb)@SRGB_XYZ.T@cat(D65,D50).T
    return xyz_lab(xyz)

def lab_rgb(lab, white=D50):
    return srgb_encode(lab_xyz(lab,white)@cat(white,D65).T@np.linalg.inv(SRGB_XYZ).T)

def delta_e00(lab1,lab2):
    """CIEDE2000, kL=kC=kH=1, Sharma/Wu/Dalal 2005 equations."""
    p,q=np.asarray(lab1,dtype=float),np.asarray(lab2,dtype=float)
    L1,a1,b1=np.moveaxis(p,-1,0); L2,a2,b2=np.moveaxis(q,-1,0)
    C1=np.hypot(a1,b1); C2=np.hypot(a2,b2); Cbar=(C1+C2)/2
    G=.5*(1-np.sqrt(Cbar**7/(Cbar**7+25.**7)))
    A1=(1+G)*a1; A2=(1+G)*a2
    c1=np.hypot(A1,b1); c2=np.hypot(A2,b2)
    h1=np.degrees(np.arctan2(b1,A1))%360; h2=np.degrees(np.arctan2(b2,A2))%360
    dl=L2-L1; dc=c2-c1; dh=h2-h1
    dh=np.where(c1*c2==0,0,np.where(dh>180,dh-360,np.where(dh < -180,dh+360,dh)))
    dH=2*np.sqrt(c1*c2)*np.sin(np.radians(dh/2))
    lbar=(L1+L2)/2; cbar=(c1+c2)/2
    hbar=np.where(c1*c2==0,h1+h2,np.where(np.abs(h1-h2)<=180,(h1+h2)/2,
             np.where(h1+h2<360,(h1+h2+360)/2,(h1+h2-360)/2)))
    T=1-.17*np.cos(np.radians(hbar-30))+.24*np.cos(np.radians(2*hbar))+\
       .32*np.cos(np.radians(3*hbar+6))-.20*np.cos(np.radians(4*hbar-63))
    Sl=1+.015*(lbar-50)**2/np.sqrt(20+(lbar-50)**2)
    Sc=1+.045*cbar; Sh=1+.015*cbar*T
    Rt=-2*np.sqrt(cbar**7/(cbar**7+25.**7))*np.sin(np.radians(60*np.exp(-((hbar-275)/25)**2)))
    v=(dl/Sl)**2+(dc/Sc)**2+(dH/Sh)**2+Rt*(dc/Sc)*(dH/Sh)
    return np.sqrt(np.maximum(v,0))

def cct_mccamy(xyz):
    """Approximation used only for dual-illuminant interpolation, not spectral truth."""
    x,y=(xyz/np.sum(xyz))[:2]
    n=(x-.3320)/(.1858-y)
    return float(449*n**3+3525*n**2+6823.3*n+5520.33)

def dng_camera_to_xyz(tags):
    """No ForwardMatrix in these GXR/GR files. Preserve actual neutral chromaticity.

    M maps XYZ to unbalanced camera RGB. The neutral fixes a relative exposure
    normalization. Do not apply AsShotNeutral gains again after using this map.
    """
    cm1=np.array(tags[50721],dtype=float).reshape(3,3)
    cm2=np.array(tags.get(50722,tags[50721]),dtype=float).reshape(3,3)
    temps={17:2856.,21:6504.,23:5003.,20:5503.}
    t1=temps[tags.get(50778,[17])[0]]; t2=temps[tags.get(50779,[21])[0]]
    neutral=np.array(tags[50728],dtype=float)
    ab=np.diag(tags.get(50727,[1,1,1]))
    signatures_match=tags.get(50931,'')==tags.get(50932,'')
    cc1=np.array(tags.get(50723,np.eye(3).ravel()) if signatures_match else np.eye(3),dtype=float).reshape(3,3)
    cc2=np.array(tags.get(50724,np.eye(3).ravel()) if signatures_match else np.eye(3),dtype=float).reshape(3,3)
    alpha=.5
    for iteration in range(100):
        cm=(1-alpha)*cm1+alpha*cm2; cc=(1-alpha)*cc1+alpha*cc2
        M=ab@cc@cm
        w=np.linalg.solve(M,neutral)
        T=cct_mccamy(w)
        new=float(np.clip((1/T-1/t1)/(1/t2-1/t1),0,1)) if t1!=t2 else 0.
        if abs(new-alpha)<1e-10:
            alpha=new; break
        alpha=(alpha+new)/2
    cm=(1-alpha)*cm1+alpha*cm2; cc=(1-alpha)*cc1+alpha*cc2
    M=ab@cc@cm
    w=np.linalg.solve(M,neutral)
    native=np.linalg.inv(M)/w[1]
    white=w/w[1]
    matrix=cat(white,D50)@native
    if 50964 in tags:
        fm1=np.array(tags[50964],dtype=float).reshape(3,3)
        fm2=np.array(tags.get(50965,tags[50964]),dtype=float).reshape(3,3)
        fm=(1-alpha)*fm1+alpha*fm2
        inv_abcc=np.linalg.inv(ab@cc)
        reference_neutral=inv_abcc@neutral
        matrix=fm@np.diag(1/reference_neutral)@inv_abcc
    return matrix,{'matrix_xyz_to_camera':M.tolist(), 'camera_to_xyz_native':native.tolist(),
        'camera_to_xyz_d50':matrix.tolist(), 'scene_white_xyz_y1':white.tolist(),
        'scene_white_xy':(white[:2]/sum(white)).tolist(), 'cct_K_approx':T,
        'interpolation_alpha_2':alpha,'iterations':iteration+1,
        'interpolation_method':'inverse-temperature; McCamy 1992 approximate CCT; endpoint-clamped',
        'neutral_check_xyz_d50':(matrix@neutral).tolist(),
        'normalization':'AsShotNeutral maps to D50 Y=1; relative sensor exposure, not absolute reflectance',
        'forward_matrix_present':50964 in tags or 50965 in tags,
        'accuracy_status':'推断: DNG colorimetric model, not measured sensor spectral characterization'}
