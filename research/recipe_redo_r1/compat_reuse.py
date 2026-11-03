"""Exact reduced-coordinate solves with byte-preserved existing shared rows."""
import copy
import hashlib
import struct
import time
import zlib
import runtime as rt
from runtime import np
from scipy.optimize import least_squares


def configure(fit, engine, solver, template, ui, family):
    import guarded_problem
    import full_confirm_support as fc
    from entry_codec import record_checks, look_identity_valid
    from gxr_studio.camdata.datcodec import CRC_FIELDS, OFFSETS, ROW_BYTES
    assert family in ('reuse_tone_matrix', 'reuse_hue_matrix') and template[1] == 1
    if not hasattr(configure,'originals'):
        configure.originals=(engine.Problem,guarded_problem.GuardedProblem,fit.seed,fit.encode,fc.starts)
    original_problem,original_guard,original_seed,original_encode,original_starts=configure.originals
    fixed_tone = family == 'reuse_tone_matrix'
    nodes = np.array([0, *struct.unpack_from('>31H', template, 20), 4095])
    tone = np.array(list(template[82:115]))
    matrix = rt.mm.MatrixRow.from_bytes(template[216:244]).coef

    def solve_reduced(problem, evaluate, start, nfev, weight=None):
        before = time.monotonic()
        start = problem.project(start)
        active = problem.active
        lower, upper = np.array(problem.lower)[active], np.array(problem.upper)[active]
        first = np.clip(start[active], lower+1e-9, upper-1e-9)
        def expand(vector):
            out = problem.fixed.copy()
            out[active] = vector
            return out
        opt = least_squares(lambda v:evaluate(expand(v))[0], first,
            jac=lambda v:evaluate(expand(v))[1][:, active], bounds=(lower, upper),
            max_nfev=nfev, x_scale='jac', ftol=2e-6, xtol=2e-6, gtol=2e-5)
        status = dict(success=bool(opt.success), status=int(opt.status), nfev=int(opt.nfev),
            njev=int(opt.njev), cost=float(opt.cost), optimality=float(opt.optimality),
            seconds=time.monotonic()-before, message=opt.message,
            compact_family=family, active_coordinates=active.tolist(),
            fixed_row_sha256=hashlib.sha256(template).hexdigest(),
            reduced_solver='scipy TRF/SVD', fixed_coordinates_projected_before_solve=True)
        if weight is not None:status['fixture_penalty_weight']=weight
        return expand(opt.x), status

    class ReuseProblem(original_problem):
        def __init__(self, camera, *args, **kwargs):
            camera=copy.copy(camera)
            camera.row=rt.mm.MatrixRow.from_bytes(template[216:244])
            camera.curve=rt.mm.Curve(nodes, camera.curve.ys)
            super().__init__(camera, *args, **kwargs)
            assert not self.bw and self.level == 0
            self.fixed=original_seed(self, template)
            self.active=np.arange(2,50) if fixed_tone else np.arange(self.qstart,self.qend)
            self.fixed_columns=np.setdiff1d(np.arange(self.np),self.active)
            self.config.update(compact_family=family,active_coordinates=self.active.tolist(),
                fixed_coordinates=self.fixed_columns.tolist(),
                fixed_reference_record_sha256=hashlib.sha256(template).hexdigest(),
                fixed_tone_nodes=nodes.tolist() if fixed_tone else None)

        def project(self, vector):
            out=np.asarray(vector).copy()
            out[self.fixed_columns]=self.fixed[self.fixed_columns]
            return out

        def evaluate(self, vector):
            value,jac=super().evaluate(self.project(vector))
            jac=jac.copy();jac[:,self.fixed_columns]=0
            return value,jac

        def packed(self, vector):
            result=super().packed(self.project(vector))
            result['matrix_q10']=matrix.copy()
            result['curve_x_u12']=nodes.copy()
            if fixed_tone:
                result['curve_y_u8']=tone[None,:].copy()
            return result

        def solve(self,start=None,nfev=100):
            return solve_reduced(self,self.evaluate,self.theta0 if start is None else start,nfev)

    class ReuseGuard(original_guard):
        def solve(self,start,nfev=100):
            result,status=solve_reduced(self.P,self.evaluate,start,nfev,self.weight)
            status['remaining_continuous_penalty_pairs']=self.last_active_pairs
            return result,status

    def seed(problem,entry):return problem.project(original_seed(problem,entry))

    def encode(current,parameters,**kwargs):
        entry=bytearray(original_encode(current,parameters,**kwargs))
        frozen=[(216,56)]
        if fixed_tone:frozen += [(20,95),(456,95)]
        else:frozen += [(115,96),(20,62),(456,62)]
        for offset,length in frozen:entry[offset:offset+length]=template[offset:offset+length]
        if kwargs.get('look_unit_mask'):
            content=bytes(entry[:2])+bytes(entry[445:447])+bytes((kwargs['look_unit_mask'],))
            content+=b''.join(entry[o:o+n] for o,n in zip(OFFSETS,ROW_BYTES))
            struct.pack_into('>I',entry,4,zlib.crc32(content)&0xffffffff)
        for offset,length,crc in CRC_FIELDS:
            struct.pack_into('>I',entry,crc,zlib.crc32(entry[offset:offset+length])&0xffffffff)
        result=bytes(entry)
        assert record_checks(result)['row_crcs_valid']
        if kwargs.get('look_unit_mask'):assert look_identity_valid(result,kwargs['look_unit_mask'])
        return result

    def starts(primary,nodes,base_starts,feasible,fast_record,seed_fn,axis,manifest):
        return original_starts(primary,nodes,[(name,primary.project(v)) for name,v in base_starts],
            feasible,fast_record,seed_fn,axis,manifest)

    engine.Problem=ReuseProblem
    guarded_problem.GuardedProblem=ReuseGuard
    fit.seed=seed
    fit.encode=encode
    fc.starts=starts
