"""Observe real frozen-watch counter writes without wrapping or changing the watch function."""
import sys,types
from pathlib import Path
from write_tape import WriteTape
class AuditRow(dict):
    def __init__(self,row,tape):super().__init__(row);self.tape=tape
    def __setitem__(self,key,value):
        previous=self.get(key);super().__setitem__(key,value)
        if key in ('cpu_writes','native_memory_fill_writes','host_writes') and value!=previous:
            frame=sys._getframe(1);event=frame.f_locals.get('ev')
            if frame.f_code.co_name!='watch' or event is None:raise AssertionError('audit row was written outside the frozen watch')
            self.tape.event(event.address,event.data,event.pc,'audit:'+key+':'+event.origin)
def bind(callback,folder,recorders,root):
    if type(callback) is not types.FunctionType or callback.__code__.co_name!='watch':return
    source=callback.__globals__.get('__file__')
    if source is None or Path(source).resolve()!=root/'research/review_g126/runtime_guard.py':return
    cells=dict(zip(callback.__code__.co_freevars,callback.__closure__ or ()))
    cell=cells.get('row')
    if cell is None or type(cell.cell_contents) is not dict:return
    old=cell.cell_contents;tape=WriteTape(folder,len(recorders));recorders.append(tape);new=AuditRow(old,tape);cell.cell_contents=new
    rows=callback.__globals__['AUDITS']
    for index,row in enumerate(rows):
        if row is old:rows[index]=new;break
    else:raise AssertionError('audit counter was not in the retained evidence list')
