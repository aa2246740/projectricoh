"""Exercise the frozen engine's pure C knob application, without a device or DAT."""
import ctypes


class Request(ctypes.Structure):
    _fields_=[('amount',ctypes.c_int32),('dose',ctypes.c_int32*10),
              ('wb_method',ctypes.c_int32),('tone_method',ctypes.c_int32)]


class Stats(ctypes.Structure):
    _fields_=[('values',ctypes.c_int32*7)]


def check(C,entry,unit):
    lib=ctypes.CDLL(str(C.LOCAL/'flags_host.dylib'))
    lib.kv_apply_work.argtypes=[ctypes.c_void_p,ctypes.c_void_p,ctypes.POINTER(Request),
                               ctypes.c_void_p,ctypes.POINTER(Stats),ctypes.c_void_p]
    lib.kv_apply_work.restype=ctypes.c_int
    assert ctypes.sizeof(Request)==52 and ctypes.sizeof(Stats)==28
    stock=C.rt.Camera(C.UNITS.index(unit)).entry
    def apply(b,contrast):
        request=Request();request.amount=100;request.dose[0]=contrast
        s=ctypes.create_string_buffer(stock,552);a=ctypes.create_string_buffer(b,552)
        out=ctypes.create_string_buffer(552);work=ctypes.create_string_buffer(2288);stats=Stats()
        status=lib.kv_apply_work(s,a,ctypes.byref(request),out,ctypes.byref(stats),work)
        assert status==0,(unit,status)
        return bytes(out.raw)
    assert entry[1] in (1,7)
    assert apply(entry,0)==entry,'Neutral default must preserve every byte'
    active=apply(entry,1)
    expected=C.rt.mm.MatrixRow.from_bytes(entry[216:244]).coef
    retained=C.rt.mm.MatrixRow.from_bytes(active[216:244]).coef
    assert C.np.array_equal(expected[1:],retained[1:]),'C100 chroma must survive a tone-only adjustment'
    disabled=bytearray(entry);disabled[1]&=~1
    bad=apply(bytes(disabled),1)
    bad_matrix=C.rt.mm.MatrixRow.from_bytes(bad[216:244]).coef
    stock_matrix=C.rt.mm.MatrixRow.from_bytes(stock[216:244]).coef
    assert C.np.array_equal(bad_matrix[1:],stock_matrix[1:])
    return dict(default_all_552_bytes_identical=True,C100_chroma_retained_with_tone_adjustment=True,
                disabled_bit_counterexample_reverts_chroma_to_stock=True,
                counterexample_changes_fitted_chroma=not C.np.array_equal(expected[1:],stock_matrix[1:]),
                source_sha256=C.sha(C.LOCAL/'contract_sources/kv_math.c'),
                dylib_sha256=C.sha(C.LOCAL/'flags_host.dylib'),
                evidence_scope='Native host pure C mathematics; not firmware execution or camera acceptance')


def compare_shared_promotion(C,shared,promoted,unit,x):
    lib=ctypes.CDLL(str(C.LOCAL/'flags_host.dylib'))
    lib.kv_apply_work.argtypes=[ctypes.c_void_p,ctypes.c_void_p,ctypes.POINTER(Request),
                               ctypes.c_void_p,ctypes.POINTER(Stats),ctypes.c_void_p]
    lib.kv_apply_work.restype=ctypes.c_int
    stock=C.rt.Camera(C.UNITS.index(unit)).entry
    def apply(b,request):
        s=ctypes.create_string_buffer(stock,552);a=ctypes.create_string_buffer(b,552)
        out=ctypes.create_string_buffer(552);work=ctypes.create_string_buffer(2288);stats=Stats()
        status=lib.kv_apply_work(s,a,ctypes.byref(request),out,ctypes.byref(stats),work)
        return status,bytes(out.raw)
    requests=[]
    for amount in (0,50,100,150):
        q=Request();q.amount=amount;requests.append(q)
    for index in range(10):
        for sign in ((1,) if index==3 else (-1,1)):
            q=Request();q.amount=100;q.dose[index]=sign*1024;requests.append(q)
            if index in (5,6,9):
                q2=Request.from_buffer_copy(q);q2.wb_method=1;q2.tone_method=1;requests.append(q2)
    maximum=0.;success=0;points=0
    for q in requests:
        a,b=apply(shared,q),apply(promoted,q)
        assert a[0]==b[0]
        if a[0]:continue
        left=C.predict(a[1],x,C.UNITS.index(unit));right=C.predict(b[1],x,C.UNITS.index(unit))
        delta=float(abs(left-right).max());maximum=max(maximum,delta);assert delta==0.
        success+=1;points+=len(left)
    return dict(requests=len(requests),successful_requests=success,points=points,
                maximum_RGB_difference=maximum,
                scope='Fixed representative native C knob requests; not all knob combinations or camera execution')
