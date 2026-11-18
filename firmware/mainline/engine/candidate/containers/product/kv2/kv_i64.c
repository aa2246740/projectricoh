#include "kv_math.h"

typedef union {
    int64_t value;
    struct {
#if __BYTE_ORDER__ == __ORDER_BIG_ENDIAN__
        uint32_t hi,lo;
#else
        uint32_t lo,hi;
#endif
    } word;
} KvWide;

static KvWide negate(KvWide a)
{
    a.word.lo=0u-a.word.lo;
    a.word.hi=~a.word.hi+(a.word.lo==0);
    return a;
}

int64_t __muldi3(int64_t x,int64_t y)
{
    KvWide a,b,r;
    uint32_t a0,a1,b0,b1,t,w0,w1,w2;
    a.value=x;b.value=y;
    a0=a.word.lo&65535u;a1=a.word.lo>>16;
    b0=b.word.lo&65535u;b1=b.word.lo>>16;
    w0=a0*b0;t=a1*b0+(w0>>16);w1=t&65535u;w2=t>>16;
    w1+=a0*b1;
    r.word.lo=(w1<<16)|(w0&65535u);
    r.word.hi=a1*b1+w2+(w1>>16)+a.word.hi*b.word.lo+a.word.lo*b.word.hi;
    return r.value;
}

int64_t __divdi3(int64_t x,int64_t y)
{
    KvWide a,b,q,r;
    uint32_t bit,sign;
    int i;
    a.value=x;b.value=y;
    sign=(a.word.hi^b.word.hi)>>31;
    if(a.word.hi>>31)a=negate(a);
    if(b.word.hi>>31)b=negate(b);
    q.word.lo=q.word.hi=r.word.lo=r.word.hi=0;
    if(!(b.word.lo|b.word.hi))return q.value;
    for(i=0;i<64;i++){
        bit=a.word.hi>>31;
        a.word.hi=(a.word.hi<<1)|(a.word.lo>>31);a.word.lo<<=1;
        r.word.hi=(r.word.hi<<1)|(r.word.lo>>31);r.word.lo=(r.word.lo<<1)|bit;
        q.word.hi=(q.word.hi<<1)|(q.word.lo>>31);q.word.lo<<=1;
        if(r.word.hi>b.word.hi || (r.word.hi==b.word.hi && r.word.lo>=b.word.lo)){
            bit=r.word.lo<b.word.lo;
            r.word.lo-=b.word.lo;r.word.hi-=b.word.hi+bit;q.word.lo|=1;
        }
    }
    if(sign)q=negate(q);
    return q.value;
}
