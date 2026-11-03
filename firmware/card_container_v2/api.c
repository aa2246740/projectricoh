#include "internal.h"

Gxr2Status gxr2_validate(const uint8_t *p,size_t n,const Gxr2Trust *trust,const Gxr2Unit *u,
                       unsigned options,Gxr2View *out)
{
    Gxr2View gate; Gxr2Status s;
    s=gxr2_gate_validate(p,n,trust,u,options,&gate);
    return s==GXR2_OK?gxr2_semantic_validate(&gate,trust,out):s;
}

int gxr2_update_decide(const Gxr2View *card,const Gxr2View *installed)
{
    if(!installed || card->build_number>installed->build_number) return GXR2_INSTALL;
    if(card->build_number<installed->build_number) return GXR2_KEEP;
    return card->length==installed->length && equal(card->bytes,installed->bytes,card->length)?GXR2_KEEP:GXR2_CONFLICT;
}

const char *gxr2_status_name(Gxr2Status s)
{
    static const char *const names[]={"OK","ARGUMENT","LENGTH","VERSION","FLAGS","CRC","LAYOUT",
        "BODY_ID","RESIDENT_ID","MODULE_ID","PIN","MAP","BANK","TABLE","TWEAK","RELOCATION","PLACEHOLDER"};
    return (unsigned)s<sizeof(names)/sizeof(names[0])?names[s]:"UNKNOWN";
}
