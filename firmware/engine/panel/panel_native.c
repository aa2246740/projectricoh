#include "panel.h"

static void put32(uint8_t *p, uint32_t x)
{
    p[0]=(uint8_t)(x>>24); p[1]=(uint8_t)(x>>16);
    p[2]=(uint8_t)(x>>8); p[3]=(uint8_t)x;
}
int32_t pn_native_from_seed(void *ctx, PnPort *port, PnNativeList *n,
                            const uint32_t glyphs[PN_ROWS], uint8_t cursor)
{
    const PnNativeSeed *s=ctx; unsigned i; uint32_t descriptors,table;
    if (!s || !port || !n || !glyphs || !s->state || !s->type_descriptors ||
        !s->details || s->state_bytes!=sizeof(n->state) ||
        s->descriptor_bytes!=sizeof(n->type_descriptors) ||
        s->detail_bytes!=sizeof(n->details) || s->state[0]!=5 ||
        cursor<1 || cursor>=PN_ROWS) return RV_ARGUMENT;
    for (i=0;i<PN_ROWS;i++) if (!glyphs[i]) return RV_ARGUMENT;
    pn_copy(n->state,s->state,sizeof(n->state));
    pn_copy(n->type_descriptors,s->type_descriptors,sizeof(n->type_descriptors));
    pn_copy(n->details,s->details,sizeof(n->details));
    for (i=0;i<PN_ROWS;i++) {
        n->glyph_refs[i]=glyphs[i];
        n->labels[i]=pn_address(port,&n->glyph_refs[i],sizeof(n->glyph_refs[i]));
        if (!n->labels[i]) return RV_ARGUMENT;
    }
    descriptors=pn_address(port,n->type_descriptors,sizeof(n->type_descriptors));
    table=pn_address(port,n->labels,sizeof(n->labels));
    if (!descriptors || !table) return RV_ARGUMENT;
    put32(n->state+4,descriptors); n->state[9]=cursor; n->state[10]=cursor;
    put32(n->type_descriptors[5],table); n->type_descriptors[5][4]=PN_ROWS;
    put32(n->type_descriptors[5]+8,0); /* No hidden-item map in the private list. */
    return RV_OK;
}
