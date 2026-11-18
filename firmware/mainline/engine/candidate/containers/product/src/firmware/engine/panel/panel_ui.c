#include "panel.h"

static void header(RvBufferHeader *h, uint32_t n)
{ h->version=1; h->bytes=(uint16_t)n; h->flags=0; }
static void rows(PnPanel *p)
{
    static const char names[4][5]={"Cont","Satu","HiLt","Shad"};unsigned i;
    for(i=0;i<PN_ROWS;++i) {
        pn_zero(p->text[i],PN_COLUMNS+1);pn_copy(p->text[i],names[p->parameter],4);
        if(p->parameter==3) {
            pn_copy(p->text[i],"Shadow",6);p->text[i][6]=i<5?'-':'+';
            p->text[i][7]=(char)('0'+(i<5?5-i:i-5));
        } else {
            p->text[i][4]=' ';p->text[i][5]=i<5?'-':'+';
            p->text[i][6]=(char)('0'+(i<5?5-i:i-5));
        }
    }
    if(p->last_store!=RV_OK)pn_copy(p->text[0],"SaveFail",9);
}
static int32_t ui_call(PnPanel *p, uint32_t svc, uint32_t op,
                       void *buffer, uint32_t bytes, uint32_t b, RvReply *r)
{
    static RvRequest q;
    pn_request(p->port,&q,p->port->ui_lease);
    q.args[9]=b; q.args[10]=pn_address(p->port,buffer,bytes); q.args[11]=bytes;
    if (!q.args[10]) return RV_ARGUMENT;
    return pn_call(p->port,svc,op,&q,r);
}
int32_t pn_ui_render(PnPanel *p, int initial)
{
    unsigned i,n;
    uint32_t lang;static uint32_t addresses[PN_ROWS];
    static RvReply r; static RvRequest q; int32_t v;
    if (!p->ops.build) return RV_UNSUPPORTED;
    if (p->stop_requested) return RV_STALE;
    rows(p);
    pn_request(p->port,&q,p->port->ui_lease);
    v=pn_call(p->port,RV_UI_TEXT,2,&q,&r);
    if (v!=RV_OK || r.native_result<0) return v==RV_OK ? RV_VERIFY : v;
    lang=r.detail;
    for (i=0;i<PN_ROWS;i++) {
        RvUiText *t=&p->text_request;
        if (p->stop_requested) return RV_STALE;
        pn_zero(t,sizeof(*t)); header(&t->header,sizeof(*t));
        for (n=0;n<PN_COLUMNS && p->text[i][n];n++) {}
        if(p->text[i][n])return RV_VERIFY;
        t->source_address=pn_address(p->port,p->text[i],n+1); t->source_bytes=n;
        t->source_lease=p->port->ui_lease;
        t->glyph_address=pn_address(p->port,p->glyph[i],PN_GLYPH_BYTES);
        t->glyph_capacity=PN_GLYPH_BYTES; t->glyph_lease=p->port->ui_lease;
        t->language=lang;
        if (!t->source_address || !t->glyph_address) return RV_ARGUMENT;
        v=ui_call(p,RV_UI_TEXT,1,t,sizeof(*t),0,&r);
        if (v!=RV_OK) return v;
        if (r.native_result<0) return RV_IO;
        if (!t->actual_bytes || t->actual_bytes>PN_GLYPH_BYTES) return RV_VERIFY;
        addresses[i]=t->glyph_address;
    }
    v=p->ops.build(p->ops.build_context,p->port,&p->native,addresses,p->cursor);
    if (v!=RV_OK) return v;
    if (p->stop_requested) return RV_STALE;
    header(&p->list.header,sizeof(p->list));
    p->list.view_token=p->view_token;
    p->list.state_address=pn_address(p->port,p->native.state,sizeof(p->native.state));
    p->list.state_bytes=sizeof(p->native.state); p->list.rows=PN_ROWS;
    p->list.cursor=p->cursor;
    p->list.label_table=pn_address(p->port,p->native.labels,sizeof(p->native.labels));
    p->list.details=pn_address(p->port,p->native.details,sizeof(p->native.details));
    p->list.lease_token=p->port->ui_lease;
    if (!p->list.state_address || !p->list.label_table || !p->list.details) return RV_ARGUMENT;
    if (initial) {
        header(&p->view.header,sizeof(p->view));
        p->view.view_token=0;
        p->view.part=2; p->view.tag=33;
        p->view.state_address=p->list.state_address;
        p->view.state_bytes=p->list.state_bytes;
        p->view.lease_token=p->port->ui_lease;
        /* Set pinned BEFORE a call that may publish a native pointer. */
        p->ui_pinned=1;
        v=ui_call(p,RV_UI_VIEW,1,&p->view,sizeof(p->view),0,&r);
        if (v!=RV_OK) return v;
        if (!p->view.view_token) p->view.view_token=r.token;
        if (!p->view.view_token || (r.token && r.token!=p->view.view_token)) return RV_VERIFY;
        p->view_token=p->view.view_token;
        p->list.view_token=p->view_token; p->view_owned=1;
    }
    if (p->stop_requested) return RV_STALE;
    p->bound=1; /* A malformed reply may follow a successful native bind. */
    v=ui_call(p,RV_UI_LIST,1,&p->list,sizeof(p->list),PN_ROWS,&r);
    if (v!=RV_OK) return v;
    if (p->stop_requested) return RV_STALE;
    v=ui_call(p,RV_UI_LIST,2,&p->list,sizeof(p->list),PN_ROWS,&r);
    if (v==RV_OK && p->stop_requested) return RV_STALE;
    if (v==RV_OK) v=ui_call(p,RV_UI_LIST,3,&p->list,sizeof(p->list),PN_ROWS,&r);
    return v;
}
int32_t pn_ui_detach(PnPanel *p)
{
    static RvReply r; int32_t a=RV_OK,b=RV_OK,c=RV_OK;
    if (!p->ui_pinned) return RV_OK;
    /* Ownership checks and the original eight-byte record live in resident. */
    if (p->view_owned) a=ui_call(p,RV_UI_VIEW,2,&p->view,sizeof(p->view),0,&r);
    if (!p->view_owned || a!=RV_OK)
        b=ui_call(p,RV_UI_VIEW,3,&p->view,sizeof(p->view),0,&r);
    if (b!=RV_OK) return b; /* Retain every buffer and block a new open. */
    if (p->bound) c=ui_call(p,RV_UI_LIST,4,&p->list,sizeof(p->list),PN_ROWS,&r);
    if (c!=RV_OK) return c;
    p->bound=0; p->view_owned=0; p->ui_pinned=0; p->view_token=0;
    return RV_OK;
}
