"""Names only. The target compiler supplies every offset and size."""
STATE=('stage level l3_count used armed arm_tick arm_stage arm_on status locked pending ref_count ref_running ref_start '
       'page result_index ref_index cursor selftest empty_ticks init_ticks table_crc table_ok unit_tag guard_before '
       'row guard_after consumed_checksum refs samples text init_phase init_offset init_crc init_slices init_last init_max init_bound init_aborts').split()
SAMPLE=('stage on level target_rows pairs expected_pairs h40 h41 kernel_start kernel_end kernel_ticks checksum '
        'status encoder h41_seen h41_irq valid full slot width height stride source_base outer sp heap_block heap_bytes budget delta_valid increment').split()
REFERENCE='start end delta valid'.split()
FRAME='pixels geometry_ok slot width height stride outer sp heap_block heap_bytes'.split()
ROOT='magic version state inflight epoch block inverse lease lease_inverse heap_begin heap_end block_bytes alloc_bytes code_address code_bytes code_crc flags unit image_state reserved_lane'.split()
SESSION=('entries context leases image_address image_bytes bss_bytes entry_offset selected_source generation source_bytes '
         'capabilities code_begin code_end crc unit settings bindings view_state view_lease list details rows cursor redraw '
         'view_source call_request call_reply image_request image_reply k_save').split()
CONTEXT=('header root_address root_bytes session_address session_bytes state_address state_bytes state_lease image_address '
         'image_bytes image_lease code_address code_bytes image_bss_bytes nonce ui_state_address ui_state_bytes ui_state_capacity '
         'entries_address entries_bytes lease_max_bytes').split()

def definitions():
    rows=[]
    for prefix,ctype,fields in (('state','LpState',STATE),('sample','LpSample',SAMPLE),('reference','LpReference',REFERENCE),
        ('frame','LpFrame',FRAME),('root','RvRoot',ROOT),('session','RvSession',SESSION),('context','RvPrivateContext',CONTEXT)):
        rows.append((prefix+'.size','sizeof('+ctype+')'))
        rows += [(prefix+'.'+name,'offsetof('+ctype+','+name+')') for name in fields]
    rows += [('root.address','RV_ROOT'),('root.magic_value','RV_ROOT_MAGIC'),('root.version_value','RV_ROOT_VERSION'),
             ('session.bytes','RV_SESSION_BYTES'),('block.overhead','RV_BLOCK_OVERHEAD')]
    return rows
