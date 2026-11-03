#include "resident.h"
GxrceStatus rv_validate(const uint8_t *p, size_t n, const GxrceTrust *t,
                        const GxrceUnit *u, GxrceView *v)
{ return gxrce_validate(p,n,t,u,0,v); }
