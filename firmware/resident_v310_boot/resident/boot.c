#include "resident.h"

static uint32_t boot_word(RvRoot *r)
{ return *(volatile uint32_t *)&r->reserved_lane; }

static void boot_flags(RvRoot *r,uint32_t clear,uint32_t set)
{
    uint32_t irq=rv_irq_save();
    r->reserved_lane=(boot_word(r)&~clear)|set;
    rv_irq_restore(irq);
}

static void finish(RvRoot *r,uint32_t result,uint32_t error)
{
    uint32_t irq=rv_irq_save();
    uint32_t w=boot_word(r)&(BO_SEEN|BO_ATTEMPTED|BO_CANCEL|BO_DIRTY|BO_GUARD);
    if(result==BO_TARGET||result==BO_PURE04)w&=~(BO_DIRTY|BO_GUARD);
    if(result==BO_ERROR)w|=BO_GUARD;
    r->reserved_lane=w|(result<<8)|(error<<16);
    rv_irq_restore(irq);
}

void rv_boot_retired(RvRoot *r)
{
    if(rv_root_valid(r)&&(boot_word(r)&(BO_BUSY|BO_DIRTY)))
        finish(r,BO_ERROR,BO_ERR_DAT);
}

void rv_boot_latch(RvRoot *r)
{
    /* H50 runs after the state-32 call to the native state setter returns.
     * No DAT call or parameter write takes place here. */
    if(RV_WORD(0x205d9c00)!=5||!rv_root_acquire(r))return;
    if(!boot_word(r))r->reserved_lane=BO_SEEN|BO_PENDING;
}

int rv_boot_shot(RvRoot *r)
{
    uint32_t irq,w;int allow;
    if(!rv_root_valid(r))return 0;
    irq=rv_irq_save();w=boot_word(r);
    allow=!(w&(BO_BUSY|BO_DIRTY|BO_GUARD));
    if(w&BO_BUSY)r->reserved_lane=w|BO_CANCEL;
    rv_irq_restore(irq);
    return allow;
}

static uint32_t call_boot(RvRoot *r,RvSession *s,uint32_t phase,uint32_t permission)
{
    RvRequest *q=&s->call_request;RvReply *p=&s->call_reply;int32_t rc;
    if(r->inflight)return BO_ERROR;
    rv_clear(q,sizeof(*q));q->args[8]=RV_BOOT_OP;q->args[9]=phase;
    q->args[12]=permission;q->args[13]=RV_ROOT+offsetof(RvRoot,reserved_lane);
    rc=rv_engine(r,s->entries.panel_event,q,p);
    /* rv_engine has checked the session after return. Never read p after
     * retirement, even if a previously published address is still mapped. */
    if(rc!=RV_CONSUMED||r->state!=RV_READY||rv_session(r)!=s||p->status!=RV_OK||
       p->token!=r->lease||p->epoch!=r->epoch[RV_UNIT_E])return BO_ERROR;
    if(phase==RV_BOOT_PREPARE&&p->detail==BO_PREPARED&&p->actual!=RV_BOOT_QUALIFIED)
        return BO_ERROR;
    return p->detail;
}

void boot_step(RvRoot *r)
{
    RvSession *s;uint32_t result,w;
    if(!rv_root_valid(r)||(boot_word(r)&(BO_PENDING|BO_ATTEMPTED))!=BO_PENDING)return;
    r->reserved_lane=(boot_word(r)&~BO_PENDING)|BO_ATTEMPTED;
    if(boot_word(r)&(BO_DIRTY|BO_GUARD))goto failed;
    if(RV_WORD(0x205d9c00)!=5||rv_boot_proven()!=BO_PROVEN_ALL){
        finish(r,BO_SKIPPED,BO_ERR_EVIDENCE);return;
    }
    if(RV_BYTE(0x205d9aa3)||RV_BYTE(0x205da00b)){
        finish(r,BO_SKIPPED,BO_ERR_MY);return;
    }
    if(r->state==RV_DISABLED_UNTIL_REBOOT||r->inflight||
       (r->flags&(RF_STOP|RF_BUSY|RF_UNCERTAIN))||rv_check(r))goto failed;
    boot_flags(r,0,BO_BUSY|BO_GUARD);
    if(r->state!=RV_READY&&rv_load(r,&rv_trust))goto failed;
    s=rv_session(r);if(!s)goto failed;
    result=call_boot(r,s,RV_BOOT_PREPARE,0);
    if(result==BO_PURE04){finish(r,result,0);return;}
    if(result!=BO_PREPARED||RV_BYTE(0x205d9aa3)||RV_BYTE(0x205da00b))goto failed;
    if(boot_word(r)&BO_CANCEL){finish(r,BO_PURE04,0);return;}
    /* Conservatively mark dirty before granting the first write, so even
     * a DAT that disappears before its first reply leaves the fixed guard. */
    boot_flags(r,0,BO_DIRTY|BO_PERMIT);
    result=call_boot(r,s,RV_BOOT_APPLY,RV_BOOT_PERMISSION);
    w=boot_word(r);boot_flags(r,BO_PERMIT,0);
    if(r->state!=RV_READY||rv_session(r)!=s)goto failed;
    if((w&BO_CANCEL)||(result!=BO_TARGET&&result!=BO_PURE04)){
        /* One compensation attempt; no retry and no recursive DAT call in
         * the shot guard. The cancelled request is never replayed. */
        result=call_boot(r,s,RV_BOOT_CANCEL,RV_BOOT_RESTORE04);
        if(result!=BO_PURE04)goto failed;
    }
    finish(r,result,0);return;
failed:
    finish(r,BO_ERROR,BO_ERR_DAT);rv_retire(r,RV_CHECK_SESSION);
}
