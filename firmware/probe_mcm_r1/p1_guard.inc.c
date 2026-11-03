/* Called only after rv_irq_save, immediately before capture and publication. */
static int probe_p1_capture(RvRoot *r,const RvRequest *q,uint32_t lease,uint32_t source,uint32_t bytes)
{
    RvSession *s=rv_session(r);uint32_t array,count,top,state,*v=r->ui_restore,i;
    if(!s||!current(r,q)||r->state!=RV_READY||!(s->capabilities&CAP_UI)||
       !rv_range(r,lease,source,bytes)||!rv_ui_snapshot(r)||
       s->ui_lengths[15]!=0x4c414e47u||s->ui_lengths[14]!=RV_BYTE(0x2023eab8)||
       RV_WORD(0x205d9bf8)!=8||RV_WORD(0x205d9c00)!=56||RV_BYTE(0x205a280f)!=2||
       RV_WORD(0x2022f720)!=0x2022f56c)return 0;
    array=RV_WORD(0x205a27d8);count=RV_BYTE(0x205a27d4);
    if(array!=RV_NATIVE_VIEWS||count<1||count>2)return 0;
    top=array+8*(count-1);state=RV_WORD(top+4);
    if(count==2&&RV_BYTE(array)!=32)return 0;
    if(!(count==1&&RV_BYTE(top)==32)&&
       (RV_BYTE(top)!=33||(state!=0x2022f71c&&state!=r->ui_block)))return 0;
    if(!v[0]){
        for(i=0;i<14;++i)if(v[i])return 0;
        if(RV_WORD(0x2022f5a8)!=0x2022d610||RV_BYTE(0x2022f5ac)!=7||
           RV_BYTE(0x2022f725)<1||RV_BYTE(0x2022f725)>7||
           RV_BYTE(0x2022f726)<1||RV_BYTE(0x2022f726)>7||
           (count==2&&state!=0x2022f71c))return 0;
    }else if(v[0]!=0x2022d610||v[1]!=7||v[10]<1||v[10]>7||v[11]<1||v[11]>7||
             v[8]!=r->epoch[RV_VIEW_E]||v[9]!=lease||s->view_lease!=lease||
             RV_WORD(0x2022f5a8)!=v[6]||RV_BYTE(0x2022f5ac)!=8||
             s->rows!=8||s->view_source!=source)return 0;
    if(!rv_ui_capture(r))return 0;
    v[8]=r->epoch[RV_VIEW_E];v[9]=lease;
    return 1;
}
