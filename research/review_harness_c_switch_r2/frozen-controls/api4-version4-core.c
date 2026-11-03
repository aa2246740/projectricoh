#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <stdint.h>
#include <string.h>
#include "operations.h"
#include "method_guard.inc.h"

/* All execution state belongs to the calling backend. The GIL stays held. */
typedef struct {
    int code, d, s, base, mode;
    int64_t immediate;
    PyObject *name, *args, *source;
} Operation;
typedef struct Instruction {
    PyObject *row, *assembly;
    uint64_t pending_visits; uint32_t visit_pc; struct Instruction *dirty_next;
    unsigned char raw[4];
    Py_ssize_t width, count;
    int parallel;
    Operation operation[2];
} Instruction;
typedef struct { uint32_t pc; PyObject *assembly,*row; } TailRow;
typedef struct { uint64_t base,end; unsigned char *bytes; int writable; } NativeRegion;
typedef struct {
    PyObject *protocol; int protocol_changed;
    PyObject *owner, *core, *regs, *regions, *mmio, *breakpoints, *rows, *cache;
    PyObject *visits, *tail, *ops, *calls, *observer, *traces, *write_filters;
    int filter_enabled;
    PyTypeObject *counter_type, *tail_type;
    uint64_t fast_writes, state_steps, deferred_steps;
    uintptr_t validated_visits,validated_ops; uint64_t visits_version,ops_version,validation_entries;
    int counters_ok;
    int stats_enabled,tail_start,tail_length,tail_dirty,op_length;
    uint64_t op_delta[74]; unsigned char op_dirty[74]; int op_order[74];
    Instruction *dirty_head,*dirty_tail; TailRow tail_data[16];
    int state_enabled,state_valid,writer_valid,regions_valid;
    uint32_t reg_data[16],pc_data,psw_data,bpsw_data,bbpsw_data,current_pc_data,writer_data;
    uint64_t acc_data;
    NativeRegion *region_data; Py_ssize_t region_count;
} Context;

static int stats_pull(Context *c);
static int stats_flush(Context *c);
static void stats_clear(Context *c);
static int state_pull(Context *c);
static int state_flush(Context *c);

static void clear_context(Context *c) {
    c->state_valid=0;
    stats_clear(c);
    PyMem_Free(c->region_data); c->region_data=NULL; c->region_count=0; c->regions_valid=0;
    Py_CLEAR(c->core); Py_CLEAR(c->regs); Py_CLEAR(c->regions); Py_CLEAR(c->mmio);
    Py_CLEAR(c->breakpoints); Py_CLEAR(c->rows); Py_CLEAR(c->cache);
    Py_CLEAR(c->traces); Py_CLEAR(c->write_filters);
    Py_CLEAR(c->visits); Py_CLEAR(c->tail); Py_CLEAR(c->ops); Py_CLEAR(c->calls); Py_CLEAR(c->observer);
}
static PyObject *context_attr(Context *c,PyObject *object,const char *name) {
    if(!c->protocol_changed)return PyObject_GetAttrString(object,name);
    PyObject **dict=_PyObject_GetDictPtr(object),*value=dict&&*dict&&PyDict_CheckExact(*dict)?PyDict_GetItemString(*dict,name):NULL;
    if(!value)value=Py_None;Py_INCREF(value);return value;
}
static int refresh(Context *c) {
    int valid=method_protocol_valid(c->protocol,c->owner);if(valid<0)return -1;
    c->protocol_changed=!valid;
    clear_context(c);
#define GET(dst, obj, name) do { c->dst = context_attr(c,obj,name); if (!c->dst) return -1; } while (0)
    GET(core,c->owner,"core"); GET(regs,c->core,"r"); GET(regions,c->owner,"regions");
    GET(mmio,c->owner,"mmio"); GET(breakpoints,c->owner,"breakpoints"); GET(rows,c->owner,"rows");
    GET(cache,c->owner,"_c_rows"); GET(visits,c->owner,"visits"); GET(tail,c->owner,"tail");
    GET(traces,c->owner,"traces"); GET(write_filters,c->owner,"_c_trace_guards");
    PyObject *enabled=context_attr(c,c->owner,"_c_filter_enabled"); if (!enabled) return -1;
    c->filter_enabled=PyObject_IsTrue(enabled); Py_DECREF(enabled); if (c->filter_enabled<0) return -1;
    PyObject *state=context_attr(c,c->owner,"_c_native_active"); if (!state) return -1;
    c->state_enabled=PyObject_IsTrue(state); Py_DECREF(state); if (c->state_enabled<0) return -1;
    GET(ops,c->core,"ops"); GET(calls,c->core,"calls"); GET(observer,c->owner,"instruction_observer");
#undef GET
    if(c->protocol_changed){c->state_enabled=0;c->stats_enabled=0;c->counters_ok=0;return 0;}
    if (state_pull(c)<0) return -1;
    return stats_pull(c);
}
static int refresh_active(Context *c,PyObject *active) {
    if (refresh(c)<0) return -1;
    if (c->core==active) return 0;
    Py_DECREF(c->core); c->core=active; Py_INCREF(active);
    Py_CLEAR(c->regs); Py_CLEAR(c->ops); Py_CLEAR(c->calls);
    c->regs=context_attr(c,active,"r");
    c->ops=context_attr(c,active,"ops");
    c->calls=context_attr(c,active,"calls");
    if (!c->regs || !c->ops || !c->calls) return -1;
    if(c->protocol_changed){c->state_enabled=0;c->stats_enabled=0;c->counters_ok=0;return 0;}
    if(state_pull(c)<0)return -1;
    return stats_pull(c);
}
static int compatible(Context *c) {
    if (state_flush(c)<0) return -1;
    if (!c->counters_ok) return 0;
    PyObject *value = PyObject_CallMethod(c->owner,"_c_compatible",NULL);
    if (!value) return -1;
    int result = PyObject_IsTrue(value); Py_DECREF(value); return result;
}
static uint32_t reg_value(Context *c, int index) {
    if (c->state_enabled && c->state_valid) return c->reg_data[index];
    return (uint32_t)PyLong_AsUnsignedLongMask(PyList_GET_ITEM(c->regs,index));
}
static int set_reg(Context *c,int index,uint32_t value) {
    if(c->protocol_changed){
        PyObject *regs=PyObject_GetAttrString(c->core,"r"),*key=PyLong_FromLong(index),*number=PyLong_FromUnsignedLong(value);
        int result=regs&&key&&number?PyObject_SetItem(regs,key,number):-1;
        Py_XDECREF(regs);Py_XDECREF(key);Py_XDECREF(number);return result;
    }
    if (c->state_enabled && c->state_valid) { c->reg_data[index]=value; return 0; }
    PyObject *number=PyLong_FromUnsignedLong(value);
    if (!number) return -1;
    if (PyList_CheckExact(c->regs)) return PyList_SetItem(c->regs,index,number);
    if (state_flush(c)<0) { Py_DECREF(number); return -1; }
    PyObject *active=c->core,*regs=c->regs; Py_INCREF(active); Py_INCREF(regs);
    PyObject *key=PyLong_FromLong(index); c->state_valid=0;
    int status=key ? PyObject_SetItem(regs,key,number) : -1;
    Py_XDECREF(key); Py_DECREF(number); Py_DECREF(regs);
    if (!status) status=refresh_active(c,active);
    Py_DECREF(active); return status;
}
static int set_u32(PyObject *obj,const char *name,uint32_t value) {
    PyObject *number=PyLong_FromUnsignedLong(value); if (!number) return -1;
    int result=PyObject_SetAttrString(obj,name,number); Py_DECREF(number); return result;
}
static int get_u32(PyObject *obj,const char *name,uint32_t *value) {
    PyObject *number=PyObject_GetAttrString(obj,name); if (!number) return -1;
    *value=(uint32_t)PyLong_AsUnsignedLongMask(number); Py_DECREF(number);
    return PyErr_Occurred() ? -1 : 0;
}
static int set_acc(Context *c,uint64_t value) {
    if (c->state_enabled && c->state_valid) { c->acc_data=value; return 0; }
    PyObject *number=PyLong_FromUnsignedLongLong(value); if (!number) return -1;
    int result=PyObject_SetAttrString(c->core,"acc",number); Py_DECREF(number); return result;
}
static int get_acc(Context *c,uint64_t *value) {
    if (c->state_enabled && c->state_valid) { *value=c->acc_data; return 0; }
    PyObject *number=PyObject_GetAttrString(c->core,"acc"); if (!number) return -1;
    *value=PyLong_AsUnsignedLongLong(number); Py_DECREF(number); return PyErr_Occurred() ? -1 : 0;
}
#include "state.inc.h"

static int increment(Context *c,PyObject *counter,PyObject *key) {
    PyObject *old=PyDict_Check(counter) ? PyDict_GetItemWithError(counter,key) : NULL;
    if (!old && PyErr_Occurred()) return -1;
    if (c->protocol_changed || Py_TYPE(counter)!=c->counter_type || (old && !PyLong_CheckExact(old))) {
        if (state_flush(c)<0) return -1;
        PyObject *active=c->core; Py_INCREF(active); Py_INCREF(counter);
        c->state_valid=0;
        PyObject *value=PyObject_GetItem(counter,key),*one=NULL,*sum=NULL;
        if (value) one=PyLong_FromLong(1);
        if (one) sum=PyNumber_Add(value,one);
        int result=sum ? PyObject_SetItem(counter,key,sum) : -1;
        Py_XDECREF(value); Py_XDECREF(one); Py_XDECREF(sum); Py_DECREF(counter);
        if (!result) result=refresh_active(c,active);
        Py_DECREF(active); return result;
    }
    PyObject *one=PyLong_FromLong(1); if (!one) return -1;
    PyObject *value=old ? PyNumber_Add(old,one) : one;
    if (old) Py_DECREF(one);
    if (!value) return -1;
    int result=PyDict_SetItem(counter,key,value); Py_DECREF(value);
    if (!result) {
        if (counter==c->visits) { c->validated_visits=(uintptr_t)counter; c->visits_version=((PyDictObject *)counter)->ma_version_tag; }
        if (counter==c->ops) { c->validated_ops=(uintptr_t)counter; c->ops_version=((PyDictObject *)counter)->ma_version_tag; }
    }
    return result;
}
#include "stats.inc.h"

static int condition(Context *c,int value) {
    uint32_t psw; if (core_get(c,"psw",&psw)<0) return -1;
    return core_set(c,"psw",(psw & ~1u) | (value != 0));
}

/* Return 1 only for ordinary mapped bytes. Every boundary uses the Python path. */
static int plain_read(Context *c,uint32_t address,unsigned size,uint32_t *value) {
    if ((uint64_t)address+size > UINT64_C(0x100000000) || (size>1 && address%size)) return 0;
    if (!PyList_CheckExact(c->mmio) || !PyList_CheckExact(c->regions)) return 0;
    for (Py_ssize_t i=0;i<PyList_GET_SIZE(c->mmio);++i) {
        PyObject *r=PyList_GET_ITEM(c->mmio,i);
        if (!PyTuple_CheckExact(r) || PyTuple_GET_SIZE(r)!=4) return 0;
        uint64_t lo=PyLong_AsUnsignedLongLong(PyTuple_GET_ITEM(r,0));
        uint64_t hi=PyLong_AsUnsignedLongLong(PyTuple_GET_ITEM(r,1));
        if (PyErr_Occurred()) return -1;
        if (lo<=address && (uint64_t)address+size<=hi) return 0;
    }
    if (c->regions_valid) {
        for (Py_ssize_t i=c->region_count;i-->0;) {
            NativeRegion *r=&c->region_data[i];
            if (r->base<=address && (uint64_t)address+size<=r->end) {
                uint32_t result=0;
                for (unsigned j=0;j<size;++j) result=(result<<8)|r->bytes[(uint64_t)address-r->base+j];
                *value=result; return 1;
            }
        }
        return 0;
    }
    for (Py_ssize_t i=PyList_GET_SIZE(c->regions);i-->0;) {
        PyObject *r=PyList_GET_ITEM(c->regions,i);
        if (!PyTuple_CheckExact(r) || PyTuple_GET_SIZE(r)!=3) return 0;
        uint64_t base=PyLong_AsUnsignedLongLong(PyTuple_GET_ITEM(r,0));
        if (PyErr_Occurred()) return -1;
        PyObject *data=PyTuple_GET_ITEM(r,1);
        Py_ssize_t length;
        const unsigned char *bytes;
        if (PyByteArray_CheckExact(data)) { length=PyByteArray_GET_SIZE(data); bytes=(unsigned char *)PyByteArray_AS_STRING(data); }
        else if (PyBytes_CheckExact(data)) { length=PyBytes_GET_SIZE(data); bytes=(const unsigned char *)PyBytes_AS_STRING(data); }
        else return 0;
        if (base<=address && (uint64_t)address+size<=base+(uint64_t)length) {
            uint32_t result=0;
            for (unsigned j=0;j<size;++j) result=(result<<8)|bytes[(uint64_t)address-base+j];
            *value=result; return 1;
        }
    }
    return 0;
}
static int memory_read(Context *c,uint32_t address,unsigned size,uint32_t *value,int *boundary) {
    int simple=plain_read(c,address,size,value); if (simple) return simple<0 ? -1 : 0;
    if (state_flush(c)<0) return -1;
    PyObject *active=c->core; Py_INCREF(active);
    PyObject *result=PyObject_CallMethod(active,"read","kI",(unsigned long)address,size);
    if (!result) { c->state_valid=0; Py_DECREF(active); return -1; }
    *value=(uint32_t)PyLong_AsUnsignedLongMask(result); Py_DECREF(result);
    if (PyErr_Occurred()) { Py_DECREF(active); return -1; }
    *boundary=1;
    int status=refresh_active(c,active); Py_DECREF(active); return status;
}
#include "trace_filter.inc.h"

static int memory_write(Context *c,uint32_t address,uint32_t value,unsigned size,int *boundary) {
    int direct=try_filtered_write(c,address,value,size,boundary);
    if (direct) return direct<0 ? -1 : 0;
    if (state_flush(c)<0) return -1;
    PyObject *active=c->core; Py_INCREF(active);
    PyObject *result=PyObject_CallMethod(active,"write","kkI",(unsigned long)address,(unsigned long)value,size);
    if (!result) { c->state_valid=0; Py_DECREF(active); return -1; }
    Py_DECREF(result); *boundary=1;
    int status=refresh_active(c,active); Py_DECREF(active); return status;
}

static void destroy_code(PyObject *capsule) {
    Instruction *code=PyCapsule_GetPointer(capsule,"gxr.instruction.1");
    if (!code) { PyErr_Clear(); return; }
    Py_XDECREF(code->row); Py_XDECREF(code->assembly);
    for (Py_ssize_t i=0;i<code->count;++i) { Py_XDECREF(code->operation[i].name); Py_XDECREF(code->operation[i].args); Py_XDECREF(code->operation[i].source); }
    PyMem_Free(code);
}
static PyObject *compile_code(PyObject *module,PyObject *args) {
    (void)module;
    PyObject *row,*encoded;
    if (!PyArg_ParseTuple(args,"OO",&row,&encoded)) return NULL;
    if (!PyTuple_Check(row) || PyTuple_GET_SIZE(row)!=4 || !PyBytes_Check(PyTuple_GET_ITEM(row,0)) || !PyList_Check(PyTuple_GET_ITEM(row,1)) || !PyList_Check(encoded)) {
        PyErr_SetString(PyExc_ValueError,"invalid decoded row"); return NULL;
    }
    Py_ssize_t width=PyBytes_GET_SIZE(PyTuple_GET_ITEM(row,0)),count=PyList_GET_SIZE(encoded);
    if ((width!=2 && width!=4) || count<1 || count>2 || PyList_GET_SIZE(PyTuple_GET_ITEM(row,1))!=count) {
        PyErr_SetString(PyExc_ValueError,"invalid instruction shape"); return NULL;
    }
    Instruction *code=PyMem_Calloc(1,sizeof(*code)); if (!code) return PyErr_NoMemory();
    code->width=width; code->count=count;
    code->row=row; Py_INCREF(row);
    code->assembly=PyTuple_GET_ITEM(row,3); Py_INCREF(code->assembly);
    code->parallel=PyObject_IsTrue(PyTuple_GET_ITEM(row,2));
    memcpy(code->raw,PyBytes_AS_STRING(PyTuple_GET_ITEM(row,0)),(size_t)width);
    PyObject *capsule=PyCapsule_New(code,"gxr.instruction.1",destroy_code);
    if (!capsule) { Py_DECREF(code->row); Py_DECREF(code->assembly); PyMem_Free(code); return NULL; }
    for (Py_ssize_t i=0;i<count;++i) {
        Operation *op=&code->operation[i];
        PyObject *item=PyList_GET_ITEM(encoded,i),*pair=PyList_GET_ITEM(PyTuple_GET_ITEM(row,1),i);
        long long immediate;
        if (!PyArg_ParseTuple(item,"iiiLii",&op->code,&op->d,&op->s,&immediate,&op->base,&op->mode) || !PyTuple_Check(pair) || PyTuple_GET_SIZE(pair)!=2) { Py_DECREF(capsule); return NULL; }
        op->immediate=(int64_t)immediate;
        if (op->code<0 || (size_t)op->code>=sizeof(op_names)/sizeof(op_names[0]) || op->mode<0 || op->mode>4 || op->d<0 || op->d>15 || op->s<0 || op->s>15 || op->base<0 || op->base>15) { Py_DECREF(capsule); PyErr_SetString(PyExc_ValueError,"invalid native register"); return NULL; }
        op->source=pair; Py_INCREF(pair);
        op->name=PyTuple_GET_ITEM(pair,0); Py_INCREF(op->name);
        op->args=PyTuple_GET_ITEM(pair,1); Py_INCREF(op->args);
    }
    return capsule;
}
static int unchanged(Context *c,Instruction *code,PyObject *key,uint32_t pc) {
    PyObject *row=PyDict_GetItemWithError(c->rows,key);
    if (!row) return PyErr_Occurred() ? -1 : 0;
    if (row!=code->row || PyTuple_GET_ITEM(row,3)!=code->assembly || PyObject_IsTrue(PyTuple_GET_ITEM(row,2))!=code->parallel) return 0;
    PyObject *ops=PyTuple_GET_ITEM(row,1);
    if (!PyList_Check(ops) || PyList_GET_SIZE(ops)!=code->count) return 0;
    for (Py_ssize_t i=0;i<code->count;++i) if (PyList_GET_ITEM(ops,i)!=code->operation[i].source) return 0;
    uint32_t raw; int simple=plain_read(c,pc,(unsigned)code->width,&raw);
    if (simple<=0) return simple;
    uint32_t expected=0; for (Py_ssize_t i=0;i<code->width;++i) expected=(expected<<8)|code->raw[i];
    return raw==expected;
}
static int python_operation(Context *c,Operation *op,uint32_t pc,int *has_target,uint32_t *target) {
    if (state_flush(c)<0) return -1;
    c->state_valid=0;
    PyObject *result=PyObject_CallMethod(c->core,"op","OOk",op->name,op->args,(unsigned long)pc);
    if (!result) return -1;
    *has_target=result!=Py_None;
    if (*has_target) *target=(uint32_t)PyLong_AsUnsignedLongMask(result);
    Py_DECREF(result); if (PyErr_Occurred()) return -1;
    return refresh(c);
}
static int operation(Context *c,Operation *op,uint32_t pc,int *has_target,uint32_t *target,int *boundary) {
    uint32_t x=reg_value(c,op->d), y=reg_value(c,op->s),value=0,address=0,psw;
    uint32_t imm=(uint32_t)op->immediate;
    uint64_t accumulator,total;
    unsigned size;
    int delayed_count=(op->code==OP_ADD3 || op->code==OP_DIV || op->code==OP_REM || op->code==OP_ADDX || op->code==OP_SUBX ||
                       ((op->code==OP_ST) && (op->mode==2 || op->mode==3)) ||
                       (op->code==OP_LD && op->mode==4) || op->code>=OP_MULLO);
    if (core_set(c,"current_pc",pc)<0) return -1;
    if (!delayed_count && op_increment(c,op)<0) return -1;
#define SET(v) do { if (set_reg(c,op->d,(uint32_t)(v))<0) return -1; } while (0)
#define COND(v) do { if (condition(c,(v))<0) return -1; } while (0)
    switch(op->code) {
    case OP_NOP: break;
    case OP_PUSH:
        address=reg_value(c,15)-4; if (set_reg(c,15,address)<0 || memory_write(c,address,x,4,boundary)<0) return -1; break;
    case OP_POP:
        address=reg_value(c,15); if (memory_read(c,address,4,&value,boundary)<0) return -1;
        if (*boundary) {
            if (state_flush(c)<0) return -1;
            PyObject *active=c->core; Py_INCREF(active); c->state_valid=0;
            PyObject *finished=PyObject_CallMethod(c->owner,"_c_pop_after_read","OiI",active,op->d,value);
            if (!finished) { Py_DECREF(active); return -1; } Py_DECREF(finished);
            int status=refresh_active(c,active); Py_DECREF(active); if (status<0) return -1;
        } else { if (set_reg(c,15,reg_value(c,15)+4u)<0) return -1; SET(value); }
        break;
    case OP_MV: SET(y); break;
    case OP_LDI: case OP_LD24: SET(imm); break;
    case OP_SETH: SET(imm<<16); break;
    case OP_LD: case OP_LDUB: case OP_LDB: case OP_LDUH: case OP_LDH:
        size=op->code==OP_LD ? 4 : (op->code==OP_LDUH || op->code==OP_LDH) ? 2 : 1;
        address=reg_value(c,op->base)+(uint32_t)op->immediate;
        if (memory_read(c,address,size,&value,boundary)<0) return -1;
        if (op->mode==4 && set_reg(c,op->base,address+4)<0) return -1;
        if (op->code==OP_LDB) value=(uint32_t)(int32_t)(int8_t)value;
        if (op->code==OP_LDH) value=(uint32_t)(int32_t)(int16_t)value;
        SET(value); break;
    case OP_ST: case OP_STB: case OP_STH:
        size=op->code==OP_ST ? 4 : op->code==OP_STH ? 2 : 1;
        address=reg_value(c,op->base)+(uint32_t)op->immediate;
        if (op->mode==2) address+=4;
        if (op->mode==3) address-=4;
        if (memory_write(c,address,x,size,boundary)<0) return -1;
        if ((op->mode==2 || op->mode==3) && set_reg(c,op->base,address)<0) return -1;
        break;
    case OP_ADD: SET(x+y); break;
    case OP_SUB: SET(x-y); break;
    case OP_AND: SET(x&y); break;
    case OP_OR: SET(x|y); break;
    case OP_XOR: SET(x^y); break;
    case OP_MUL: SET(x*y); break;
    case OP_SLL: SET(x<<(y&31)); break;
    case OP_SRL: SET(x>>(y&31)); break;
    case OP_SRA: SET((int32_t)x>>(y&31)); break;
    case OP_NOT: SET(~y); break;
    case OP_NEG: SET(0u-y); break;
    case OP_DIVU: if (y) SET(x/y); break;
    case OP_REMU: if (y) SET(x%y); break;
    case OP_DIV: case OP_REM:
        if (y) { int64_t a=(int32_t)x,b=(int32_t)y,q=a/b; SET(op->code==OP_DIV ? q : a-q*b); } break;
    case OP_OR3: SET(y|imm); break;
    case OP_AND3: SET(y&imm); break;
    case OP_XOR3: SET(y^imm); break;
    case OP_ADD3:
        value=imm; if (op->immediate>=0x8000 && op->immediate<=0xffff) value=imm-0x10000;
        SET(y+value); break;
    case OP_SLL3: SET(y<<(imm&31)); break;
    case OP_SRL3: SET(y>>(imm&31)); break;
    case OP_SRA3: SET((int32_t)y>>(imm&31)); break;
    case OP_ADDI: SET(x+imm); break;
    case OP_SLLI: SET(op->immediate>=32 ? 0 : x<<imm); break;
    case OP_SRLI: SET(op->immediate>=32 ? 0 : x>>imm); break;
    case OP_SRAI: SET(op->immediate>=32 ? ((int32_t)x<0 ? UINT32_MAX : 0) : (uint32_t)((int32_t)x>>imm)); break;
    case OP_CMPU: COND(x<y); break;
    case OP_CMPUI: COND(x<imm); break;
    case OP_CMPEQ: COND(x==y); break;
    case OP_CMP: COND((int32_t)x<(int32_t)y); break;
    case OP_CMPI: COND((int32_t)x<(int32_t)imm); break;
    case OP_ADDX:
        if (core_get(c,"psw",&psw)<0) return -1;
        total=(uint64_t)x+y+(psw&1); COND(total>UINT32_MAX); SET(total); break;
    case OP_SUBX:
        if (core_get(c,"psw",&psw)<0) return -1;
        total=(uint64_t)y+(psw&1); COND((uint64_t)x<total); SET((uint64_t)x-total); break;
    case OP_BRA: case OP_BL: case OP_BC: case OP_BNC:
        if (core_get(c,"psw",&psw)<0) return -1;
        if (op->code==OP_BRA || op->code==OP_BL || !!(psw&1)==(op->code==OP_BC)) {
            if (op->code==OP_BL && set_reg(c,14,(pc&~3u)+4)<0) return -1;
            *has_target=1; *target=imm;
        } break;
    case OP_BEQZ: case OP_BNEZ: case OP_BGTZ: case OP_BLEZ: case OP_BGEZ: case OP_BLTZ:
        if ((op->code==OP_BEQZ && x==0) || (op->code==OP_BNEZ && x!=0) ||
            (op->code==OP_BGTZ && (int32_t)x>0) || (op->code==OP_BLEZ && (int32_t)x<=0) ||
            (op->code==OP_BGEZ && (int32_t)x>=0) || (op->code==OP_BLTZ && (int32_t)x<0)) { *has_target=1; *target=imm; } break;
    case OP_BEQ: case OP_BNE:
        if ((x==y)==(op->code==OP_BEQ)) { *has_target=1; *target=imm; } break;
    case OP_JMP: case OP_JL:
        *has_target=1; *target=x&~3u;
        if (op->code==OP_JL) {
            if (set_reg(c,14,(pc&~3u)+4)<0) return -1;
            if (PyList_GET_SIZE(c->calls)<4096) {
                PyObject *row=PyUnicode_FromFormat("0x%x",pc),*destination=PyUnicode_FromFormat("0x%x",*target);
                PyObject *record=(row && destination) ? Py_BuildValue("{s:O,s:O}","pc",row,"target",destination) : NULL;
                Py_XDECREF(row); Py_XDECREF(destination);
                if (!record) return -1;
                int result=PyList_Append(c->calls,record); Py_DECREF(record); if (result<0) return -1;
            }
        } break;
    case OP_MULLO: case OP_MULHI: case OP_MACLO: case OP_MACHI:
        accumulator=((uint64_t)((int64_t)(int32_t)x*(int64_t)(int32_t)y))<<16;
        if (op->code==OP_MACLO || op->code==OP_MACHI) { if (get_acc(c,&total)<0) return -1; accumulator+=total; }
        if (set_acc(c,accumulator)<0) return -1; break;
    case OP_MVFACMI: case OP_MVFACLO: case OP_MVFACHI:
        if (get_acc(c,&accumulator)<0) return -1;
        SET(accumulator>>(op->code==OP_MVFACLO ? 0 : op->code==OP_MVFACMI ? 16 : 32)); break;
    case OP_MVTACLO: case OP_MVTACHI:
        if (get_acc(c,&accumulator)<0) return -1;
        accumulator=op->code==OP_MVTACLO ? (accumulator&UINT64_C(0xffffffff00000000))|x : (accumulator&UINT32_MAX)|((uint64_t)x<<32);
        if (set_acc(c,accumulator)<0) return -1; break;
    case OP_MVFC: {
        if (state_flush(c)<0) return -1;
        c->state_valid=0;
        PyObject *result=PyObject_CallMethod(c->core,"get_cr","O",PyTuple_GET_ITEM(op->args,1));
        if (!result) return -1;
        uint32_t number=(uint32_t)PyLong_AsUnsignedLongMask(result); Py_DECREF(result);
        if (PyErr_Occurred()) return -1;
        if (refresh(c)<0) return -1; SET(number);
        *boundary=1; break;
    }
    case OP_MVTC: {
        if (state_flush(c)<0) return -1;
        c->state_valid=0;
        PyObject *result=PyObject_CallMethod(c->core,"set_cr","Ok",PyTuple_GET_ITEM(op->args,1),(unsigned long)x);
        if (!result) return -1; Py_DECREF(result);
        *boundary=1; if (refresh(c)<0) return -1; break;
    }
    default: PyErr_SetString(PyExc_RuntimeError,"unencoded native operation"); return -1;
    }
#undef SET
#undef COND
    return delayed_count ? op_increment(c,op) : 0;
}
static int observe(Context *c,uint32_t before) {
    if (c->observer==Py_None) return 0;
    if (state_flush(c)<0) return -1;
    c->state_valid=0;
    PyObject *value=PyObject_CallMethod(c->owner,"_observe","k",(unsigned long)before);
    if (!value) return -1; Py_DECREF(value); return refresh(c);
}
static PyObject *run_loop(PyObject *module,PyObject *args) {
    (void)module;
    PyObject *owner,*protocol; unsigned long long maximum,lr;
    if (!PyArg_ParseTuple(args,"OKKO",&owner,&maximum,&lr,&protocol)) return NULL;
    Context c={0}; c.owner=owner;c.protocol=protocol;
    uint64_t steps=0; uint32_t pc=0;
    PyObject *capsule=NULL,*key=NULL,*iterator=NULL;
    const char *reason="fallback"; int prepared=0;
    PyObject *initial_counter=PyObject_GetAttrString(owner,"visits"),*initial_tail=PyObject_GetAttrString(owner,"tail");
    if (!initial_counter || !initial_tail) { Py_XDECREF(initial_counter); Py_XDECREF(initial_tail); goto error; }
    c.counter_type=Py_TYPE(initial_counter); c.tail_type=Py_TYPE(initial_tail);
    Py_DECREF(initial_counter); Py_DECREF(initial_tail);
    if (refresh(&c)<0) goto error;
    for (;;) {
        if ((steps & 4095u)==0) {
            if (state_flush(&c)<0) goto error;
            if (PyErr_CheckSignals()<0) { c.state_valid=0; goto error; }
            if (refresh(&c)<0) goto error;
            int valid=compatible(&c); if (valid<0) goto error;
            if (!valid) break;
        }
        if (owner_get(&c,"pc",&pc)<0) goto error;
        if ((uint64_t)pc==lr) { reason="return"; break; }
        if (steps>=maximum) { reason="max_steps"; break; }
        if (pc>0xfffffffbu) break;
        if (owner_set(&c,"writer_pc",pc)<0) goto error;
        PyObject *origin=PyUnicode_FromString("cpu"); if (!origin) goto error;
        int set=PyObject_SetAttrString(owner,"origin",origin); Py_DECREF(origin); if (set<0) goto error;
        key=PyLong_FromUnsignedLong(pc); if (!key) goto error;
        PyObject *callbacks=PyDict_GetItemWithError(c.breakpoints,key);
        if (!callbacks && PyErr_Occurred()) goto error;
        int touched=0;
        if (callbacks) {
            if (!PyList_CheckExact(callbacks) && !PyTuple_CheckExact(callbacks)) { Py_CLEAR(key); break; }
            if (state_flush(&c)<0) goto error;
            iterator=PyObject_GetIter(callbacks); if (!iterator) goto error;
            PyObject *callback;
            while ((callback=PyIter_Next(iterator))) {
                if (state_flush(&c)<0) { Py_DECREF(callback); goto error; }
                PyObject *result=PyObject_CallFunctionObjArgs(callback,owner,NULL); Py_DECREF(callback);
                if (!result) { c.state_valid=0; goto error; }
                if (refresh(&c)<0) { Py_DECREF(result); goto error; }
                int stop=result!=Py_False; Py_DECREF(result); touched=1;
                if (stop) { reason="breakpoint"; Py_CLEAR(iterator); Py_CLEAR(key); if (owner_get(&c,"pc",&pc)<0) goto error; goto complete; }
            }
            if (PyErr_Occurred()) goto error;
            Py_CLEAR(iterator);
        }
        uint32_t current;
        if (owner_get(&c,"pc",&current)<0) goto error;
        if (touched) {
            if (refresh(&c)<0) goto error;
            int valid=compatible(&c); if (valid<0) goto error;
            if (current!=pc) {
                if (observe(&c,pc)<0) goto error;
                ++steps; if (c.state_enabled && c.state_valid) ++c.state_steps; if (c.stats_enabled) ++c.deferred_steps; Py_CLEAR(key);
                if (!valid || c.protocol_changed) break;
                continue;
            }
            if (!valid) { prepared=1; Py_CLEAR(key); break; }
        }
        PyObject *cached=PyDict_GetItemWithError(c.cache,key);
        if (!cached && PyErr_Occurred()) goto error;
        Instruction *code=NULL;
        if (cached) {
            code=PyCapsule_GetPointer(cached,"gxr.instruction.1"); if (!code) goto error;
            int valid=unchanged(&c,code,key,pc); if (valid<0) goto error;
            if (valid) { capsule=cached; Py_INCREF(capsule); }
        }
        if (!capsule) {
            uint32_t prefix; int ordinary=plain_read(&c,pc,2,&prefix);
            if (ordinary<0) goto error;
            if (!ordinary) { prepared=1; Py_CLEAR(key); break; }
            if (state_flush(&c)<0) goto error;
            capsule=PyObject_CallMethod(owner,"_c_fetch","k",(unsigned long)pc);
            if (!capsule) goto error;
            if (refresh(&c)<0) goto error;
            int valid=compatible(&c); if (valid<0) goto error;
            if (!valid) { prepared=1; Py_CLEAR(key); Py_CLEAR(capsule); break; }
            code=PyCapsule_GetPointer(capsule,"gxr.instruction.1"); if (!code) goto error;
        }
        int real=0,unsupported=0;
        for (Py_ssize_t slot=0;slot<code->count;++slot) { real+=code->operation[slot].code!=OP_NOP; unsupported|=code->operation[slot].code==OP_UNKNOWN; }
        if (unsupported || (code->parallel && real>1)) { prepared=1; Py_CLEAR(key); Py_CLEAR(capsule); break; }
        if (visit_increment(&c,code,key,pc)<0 || tail_append(&c,key,code,pc)<0) goto error;
        int has_target=0,native_ok=1,pc_handled=0; uint32_t target=0;
        for (Py_ssize_t slot=0;slot<code->count;++slot) {
            if (owner_get(&c,"pc",&current)<0) goto error;
            int boundary=0;
            if (native_ok) {
                if (operation(&c,&code->operation[slot],current+(uint32_t)(2*slot),&has_target,&target,&boundary)<0) goto error;
                if (boundary || c.protocol_changed) {
                    if (state_flush(&c)<0 || refresh(&c)<0) goto error;
                    native_ok=compatible(&c); if (native_ok<0) goto error;
                    if (!native_ok && !has_target) {
                        if (state_flush(&c)<0) goto error;
                        c.state_valid=0;
                        PyObject *finished=PyObject_CallMethod(owner,"_c_finish","Oni",PyTuple_GET_ITEM(code->row,1),slot+1,(int)code->width);
                        if (!finished) goto error;
                        Py_DECREF(finished); pc_handled=1;
                        if (refresh(&c)<0) goto error;
                        break;
                    }
                }
            } else {
                if (python_operation(&c,&code->operation[slot],current+(uint32_t)(2*slot),&has_target,&target)<0) goto error;
            }
            if (has_target) break;
        }
        if (!pc_handled && (owner_get(&c,"pc",&current)<0 || owner_set(&c,"pc",has_target ? target : current+(uint32_t)code->width)<0)) goto error;
        if (observe(&c,pc)<0) goto error;
        ++steps; if (c.state_enabled && c.state_valid) ++c.state_steps; if (c.stats_enabled) ++c.deferred_steps;
        Py_CLEAR(key); Py_CLEAR(capsule);
        if (!native_ok || c.protocol_changed) break;
    }
complete:
    if (state_flush(&c)<0) goto error;
    if (owner_get(&c,"pc",&pc)<0) goto error;
    PyObject *number=PyLong_FromUnsignedLongLong(steps); if (!number) goto error;
    int stored=PyObject_SetAttrString(owner,"_c_steps",number); Py_DECREF(number); if (stored<0) goto error;
    PyObject *actual_pc=PyObject_GetAttrString(owner,"pc");
    if (!actual_pc) goto error;
    PyObject *fast=PyLong_FromUnsignedLongLong(c.fast_writes);
    if (!fast || PyObject_SetAttrString(owner,"_c_fast_writes",fast)<0) { Py_XDECREF(fast); Py_DECREF(actual_pc); goto error; }
    Py_DECREF(fast);
    PyObject *native_count=PyLong_FromUnsignedLongLong(c.state_steps);
    if (!native_count || PyObject_SetAttrString(owner,"_c_state_steps",native_count)<0) { Py_XDECREF(native_count); Py_DECREF(actual_pc); goto error; }
    Py_DECREF(native_count);
    PyObject *deferred=PyLong_FromUnsignedLongLong(c.deferred_steps);
    if (!deferred || PyObject_SetAttrString(owner,"_c_deferred_steps",deferred)<0) { Py_XDECREF(deferred); Py_DECREF(actual_pc); goto error; }
    Py_DECREF(deferred);
    PyObject *validated=PyLong_FromUnsignedLongLong(c.validation_entries);
    if (!validated || PyObject_SetAttrString(owner,"_c_validation_entries",validated)<0) { Py_XDECREF(validated); Py_DECREF(actual_pc); goto error; }
    Py_DECREF(validated);
    clear_context(&c);
    PyObject *result=Py_BuildValue("(sOKi)",reason,actual_pc,(unsigned long long)steps,prepared);
    Py_DECREF(actual_pc); return result;
error: {
    PyObject *kind,*value,*trace; PyErr_Fetch(&kind,&value,&trace);
    if (state_flush(&c)<0) PyErr_Clear();
    PyObject *n=PyLong_FromUnsignedLongLong(steps);
    if (n) { if (PyObject_SetAttrString(owner,"_c_steps",n)<0) PyErr_Clear(); Py_DECREF(n); }
    PyObject *fast=PyLong_FromUnsignedLongLong(c.fast_writes);
    if (fast) { if (PyObject_SetAttrString(owner,"_c_fast_writes",fast)<0) PyErr_Clear(); Py_DECREF(fast); }
    PyObject *native_count=PyLong_FromUnsignedLongLong(c.state_steps);
    if (native_count) { if (PyObject_SetAttrString(owner,"_c_state_steps",native_count)<0) PyErr_Clear(); Py_DECREF(native_count); }
    PyObject *deferred=PyLong_FromUnsignedLongLong(c.deferred_steps);
    if (deferred) { if (PyObject_SetAttrString(owner,"_c_deferred_steps",deferred)<0) PyErr_Clear(); Py_DECREF(deferred); }
    Py_XDECREF(capsule); Py_XDECREF(key); Py_XDECREF(iterator); clear_context(&c);
    PyErr_Restore(kind,value,trace); return NULL;
}}
static PyMethodDef methods[]={
    {"method_guard",create_method_guard,METH_VARARGS,"Capture complete method resolution dependencies."},
    {"method_guard_same",check_method_guard,METH_VARARGS,"Compare raw MRO, defining dictionaries, functions and instance overrides."},
    {"audit_guard",create_audit_guard,METH_VARARGS,"Bind the frozen UI write early-return predicate."},
    {"trace_guard",create_trace_guard,METH_O,"Bind the frozen trace early-return predicate."},
    {"compile",compile_code,METH_VARARGS,"Encode one byte-checked decoded row."},
    {"run",run_loop,METH_VARARGS,"Execute with live Python state and synchronous boundaries."},
    {NULL,NULL,0,NULL}
};
static struct PyModuleDef definition={PyModuleDef_HEAD_INIT,"_gxr_ccore",NULL,-1,methods,NULL,NULL,NULL,NULL};
PyMODINIT_FUNC PyInit__gxr_ccore(void) {
    PyObject *module=PyModule_Create(&definition); if (!module) return NULL;
    PyObject *ops=PyDict_New(); if (!ops) { Py_DECREF(module); return NULL; }
    for (size_t i=0;i<sizeof(op_names)/sizeof(op_names[0]);++i) {
        PyObject *number=PyLong_FromSize_t(i);
        if (!number || PyDict_SetItemString(ops,op_names[i],number)<0) { Py_XDECREF(number); Py_DECREF(ops); Py_DECREF(module); return NULL; }
        Py_DECREF(number);
    }
    if (PyModule_AddObject(module,"OPCODES",ops)<0) { Py_DECREF(ops); Py_DECREF(module); return NULL; }
    if (PyModule_AddIntConstant(module,"API_VERSION",4)<0) { Py_DECREF(module); return NULL; }
    return module;
}
