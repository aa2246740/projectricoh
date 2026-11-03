#!/usr/bin/env python3
"""Existing shared-curve hardware, with at most three codes of grey-axis change."""
import os
for _k in ('OPENBLAS_NUM_THREADS','VECLIB_MAXIMUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[_k]='1'
import sys
sys.dont_write_bytecode=True
from pathlib import Path
import importlib.util
sp=importlib.util.spec_from_file_location('gr_ceiling',Path(__file__).with_name('analyze.py'))
a=importlib.util.module_from_spec(sp);sp.loader.exec_module(a)
np,opt,sparse=a.np,a.optimize,a.sparse


def main():
    a.guard()
    bw,r,K,D=a.bw_data()
    W=[r.interpolation(D['x'][:,j],D['nodes']) for j in range(3)]
    old=a.read(a.ROOT/'research/bw03_round2/metrics.json')
    baseq=bw.mm.read_stock_rows()['row1'].coef[0]
    output={};private={}
    for kind in ('stock_Y','refitted_Y'):
        fullq=baseq if kind=='stock_Y' else np.array(a.read(a.ROOT/'research/bw03_round2/local/candidate_y_only.json')['Y_q10'])
        rows=[]
        for fold in (None,0,1):
            select=np.ones(len(D['j']),bool) if fold is None else D['frame']!=fold
            q=fullq
            if fold is not None and kind=='refitted_Y':
                scene=list(bw.FRAMES)[fold]
                # q itself was fitted only on the training scene in the old run.
                q=np.array(old['Y_leave_one_scene_out'][scene]['Y_q10'])
            B=sum(W[j]*(q[j]/1024) for j in range(3))
            Bs=B[select]; js=D['j'][select]
            weight=bw.bin_weights(D['lab'][select])[0]
            H=(Bs.T @ Bs.multiply(weight[:,None])).toarray()/weight.sum()
            g=-np.asarray(Bs.T@(weight*js)).ravel()/weight.sum()
            low=np.maximum(D['curve']-3,0);hi=np.minimum(D['curve']+3,255)
            difference=np.diff(np.eye(len(low)),axis=0)
            sol=opt.minimize(lambda v:(v@H@v+2*g@v)/100,D['curve'],
                jac=lambda v:2*(H@v+g)/100,method='SLSQP',bounds=list(zip(low,hi)),
                constraints=[opt.LinearConstraint(difference,0,np.inf)],
                options={'ftol':1e-11,'maxiter':300})
            assert sol.success,sol.message
            pred=np.asarray(B@sol.x).ravel()
            out=dict(fold=fold,solver_success=bool(sol.success),iterations=int(sol.nit),
                     max_grey_axis_change_codes=float(abs(sol.x-D['curve']).max()))
            if fold is None:
                out['metrics']=a.bw_metrics(D,pred)
            else:
                test=~select;d={k:v[test] for k,v in D.items() if k in ('j','chrom')}
                d['wt']=bw.bin_weights(D['lab'][test])[0]
                out['held_out_metrics']=a.bw_metrics(d,pred[test])
            rows.append(out)
            private[f'{kind}_{fold}']=dict(q=q,shared_curve=sol.x)
        output[kind]=rows
    a.save(a.LOCAL/'bw_shared_curve_parameters.json',private)
    a.save(a.LOCAL/'bw_shared_curve_stats.json',output)
    print({k:round(v[0]['metrics']['bin_weighted_rms'],6) for k,v in output.items()})


if __name__=='__main__':main()
