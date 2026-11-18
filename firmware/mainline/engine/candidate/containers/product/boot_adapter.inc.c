/* BOOT has its own entry identity. It never publishes a menu. */
static uint32_t boot_fail_bits(void)
{
    uint32_t bits=0,settings=RV_WORD(0x200c0dac),length=RV_WORD(0x200c0db0);
    unsigned valid=settings>=0x20000000u&&settings<=0x207ff000u&&length==0x1000;
    if(RV_WORD(0x205d9bf8)!=0)bits|=BF_ACTIVITY;
    /* g172: field-confirmed PASM pairs; retain the original AUTO branch.
     * Exact selection matching also excludes movie/scene variants. */
    {
        static const uint16_t pasm[4]={0x8010,0x8020,0x8008,0x8800};
        unsigned mode=RV_BYTE(0x205d9a7f),sub=RV_BYTE(0x205d9a9f);
        if(!valid||!((mode==0&&RV_WORD(settings+0x2fc)==0x8001)||
            (mode==4&&sub<4&&RV_WORD(settings+0x2fc)==pasm[sub])))bits|=BF_MODE;
    }
    if(RV_BYTE(0x205d9aa3))bits|=BF_MY;
    if(RV_BYTE(0x205da00b))bits|=BF_PENDING;
    if(!valid)bits|=BF_SETTINGS;
    if(RV_WORD(0x205d9c00)!=5)bits|=BF_STATE;
    return bits;
}
static int boot_native_ready(void){return !boot_fail_bits();}
/* Rewrite recognized body aspect names after the unit and r5 identity checks.
 * Failed identity checks write no names. Repeated valid calls are idempotent. */
uint32_t xpan_label_result;
static int label_same(const volatile uint8_t *p,const uint8_t *q,unsigned n)
{unsigned i;for(i=0;i<n;++i)if(p[i]!=q[i])return 0;return 1;}
void xpan_label_once(void) __attribute__((noinline,used));
void xpan_label_once(void)
{
    static const uint8_t units[3][8]={
        {'q','l','a','u','n','c','h',0},
        {'j','l','a','u','n','c','h',0},
        {'l','0','8','f','i','r','m',0}
    };
    static const uint8_t old_name[5]={'1','6',':','9',0};
    static const uint8_t mark_name[5]={'E','0','3',0,0};
    static const uint8_t new_name[5]={'X','P','a','n',0};
    const volatile uint8_t *unit,*mark;
    volatile uint8_t *menu,*finder;
    unsigned i;
    /* The r5 body file hash starts 37fe29f0. That digest is not in RAM.
     * Official 1.51 is ff here; r5 has this word. Anything else writes nothing.
     * Only a matching marker authorizes access to the fixed name slots.
     * An existing E03 can be replaced by XPan after identity is verified. */
    static const uint8_t r5_mark[4]={0x20,0x7f,0x21,0x7f};
    xpan_label_result=0;
    unit=RV_PTR(0x2040f81c);
    if(!label_same(unit,units[0],8)&&!label_same(unit,units[1],8)&&!label_same(unit,units[2],8)){
        xpan_label_result=fx_image.status=2;return;}
    menu=RV_PTR(0x20222428);finder=RV_PTR(0x20223150);
    mark=RV_PTR(0x2005276c);
    for(i=0;i<4;++i)if(mark[i]!=r5_mark[i]){
        xpan_label_result=fx_image.status=3;
        return;}
    if(label_same(menu,new_name,5)&&label_same(finder,new_name,5)){
        xpan_label_result=fx_image.status=5;return;}
    if(!(label_same(menu,old_name,5)&&label_same(finder,old_name,5))&&
       !(label_same(menu,mark_name,5)&&label_same(finder,mark_name,5))){
        xpan_label_result=fx_image.status=4;return;}
    for(i=0;i<5;++i){menu[i]=new_name[i];finder[i]=new_name[i];}
    xpan_label_result=fx_image.status=5;
}
int eng_boot_check(void)
{
    RvRoot *r;RvSession *s;const uint8_t *unit=RV_PTR(0x2040f81c);unsigned i;
    if(!n.context||n.entry!=51||!n.active||!boot_native_ready())return 0;
    r=RV_PTR(n.context->root_address);s=RV_PTR(n.context->session_address);
    if(rv_services_init(n.context)!=n.api||r->state!=RV_READY||(r->flags&RF_STOP)||r->inflight!=1||
       r->lease!=n.request.args[0]||r->lease!=n.context->nonce||
       r->block!=n.context->session_address||s->context.input_fields!=51||
       s->context.input_sequence!=r->entry_serial||
       (r->reserved_lane&~4u)!=2||r->epoch[RV_MODE_E]!=boot_mode_epoch||
       RV_WORD(0x200c0dac)!=boot_settings||RV_WORD(0x200c0db0)!=boot_settings_bytes||
       boot_settings_bytes!=0x1000||RV_BYTE(boot_settings+14)!=0x0d||RV_BYTE(boot_settings+15)!=0x24||
       !RV_WORD(0x2040f804)||!pn_equal(unit,&r->unit,8)||
       rv_be16(unit+44)!=r->unit.main_version||rv_be16(unit+46)!=r->unit.cmp_version)return 0;
    for(i=0;i<4;++i)if(n.request.args[i+2]!=r->epoch[i])return 0;
    if(n.request.args[6]!=r->epoch[RV_VIEW_E]||n.request.args[7]!=r->epoch[RV_S_E])return 0;
    return 1;
}
static int32_t boot_run(const RvApi *a,uint32_t c,const RvRequest *q,RvReply *r)
{
    EngStatus status=ENG_OK;unsigned detail=2,reason=0;uint32_t bits;
    if(!ingress(a,c,q,r)){r->status=RV_STALE;return RV_FAULT;}
    diag_capture(51);bits=boot_fail_bits();
    n.entry=51;n.watch_view=n.view_lost=n.comm_failed=0;eng_view_lost(0);
    rv_settings_entry(RV_PTR(n.context->root_address),51);
    boot_mode_epoch=((RvRoot *)RV_PTR(n.context->root_address))->epoch[RV_MODE_E];
    boot_settings=RV_WORD(0x200c0dac);boot_settings_bytes=RV_WORD(0x200c0db0);
    eng_read_saved();diag_reason(0,0);
    if(q->args[9]!=0x200547ec){bits|=BF_SETTINGS;}
    /* 1 kept slot, 2 empty tail, 3 retained older catalogue, 4 empty unit slot.
     * Corrupt and unknown tails stay outside eng_boot_run. */
    {unsigned mr=eng_memory_result();
     if(mr!=1u&&mr!=2u&&mr!=3u&&mr!=4u)bits|=BF_RECORD;}
    if(boot_settings>=0x20000000u&&boot_settings<=0x207ff000u&&boot_settings_bytes==0x1000&&
       (RV_BYTE(boot_settings+8)||RV_BYTE(boot_settings+0x36e)!=1||
        RV_BYTE(boot_settings+0x6dd)!=9||RV_BYTE(boot_settings+0x6de)!=9)){
        bits|=BF_NATIVE;
    }
    {static const uint8_t reasons[]={10,11,12,13,14,15,20,21};unsigned i;
     for(i=0;i<8;++i)if(bits&(2u<<i)){reason=reasons[i];break;}}
#if !G175_BOOT
    bits|=BF_POLICY;reason=2;
#endif
    if(bits)diag_reason(reason,bits);
    else status=eng_boot_check()?eng_boot_run(RV_PTR(q->args[9]),&detail):ENG_STALE;
    /* Boot is later than init_core. The body can put 16:9 back during the
     * transaction, and a failed transaction used to skip both the rewrite
     * and the crop. Rewrite whenever the root is ready. The crop and the
     * status line share fx_frame_key's aspect, view, controller, layer and
     * alignment gate. A second redraw here used to format XPan on an empty
     * table and on 3:2. */
    {
        RvRoot *root=RV_PTR(n.context->root_address);
        if(root->state==RV_READY&&!(root->flags&(RF_STOP|RF_UNCERTAIN|RF_BUSY)))xpan_label_once();
        if(status==ENG_OK||RV_WORD(0x205d9c00u)==5u)fx_frame_key(0x29);
        else fx_mask_suspend();
    }
    n.active=0;r->detail=detail;r->status=status==ENG_OK?RV_OK:status==ENG_STALE?RV_STALE:RV_IO;
    return status==ENG_OK?RV_CONSUMED:RV_FAULT;
}
