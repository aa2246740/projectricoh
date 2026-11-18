#include "internal.h"

typedef struct {
    uint32_t state[8];
    uint32_t bytes_lo,bytes_hi;
    uint8_t block[64];
    unsigned used;
} Sha256;

static uint32_t ror(uint32_t x, unsigned n)
{ return (x >> n) | (x << (32u - n)); }

static void sha_block(Sha256 *s)
{
    static const uint32_t k[64] = {
        0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,
        0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,
        0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,
        0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,
        0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,
        0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,
        0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,
        0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2
    };
    uint32_t w[64], a,b,c,d,e,f,g,h,t1,t2,x,y;
    unsigned i;
    for (i = 0; i < 16; ++i) w[i] = be32(s->block + 4u * i);
    for (i = 16; i < 64; ++i) {
        x = w[i - 15]; y = w[i - 2];
        w[i] = w[i - 16] + (ror(x,7) ^ ror(x,18) ^ (x >> 3)) +
               w[i - 7] + (ror(y,17) ^ ror(y,19) ^ (y >> 10));
    }
    a=s->state[0]; b=s->state[1]; c=s->state[2]; d=s->state[3];
    e=s->state[4]; f=s->state[5]; g=s->state[6]; h=s->state[7];
    for (i = 0; i < 64; ++i) {
        t1 = h + (ror(e,6)^ror(e,11)^ror(e,25)) + ((e&f)^(~e&g)) + k[i] + w[i];
        t2 = (ror(a,2)^ror(a,13)^ror(a,22)) + ((a&b)^(a&c)^(b&c));
        h=g; g=f; f=e; e=d+t1; d=c; c=b; b=a; a=t1+t2;
    }
    s->state[0]+=a; s->state[1]+=b; s->state[2]+=c; s->state[3]+=d;
    s->state[4]+=e; s->state[5]+=f; s->state[6]+=g; s->state[7]+=h;
}

static void sha_init(Sha256 *s)
{
    static const uint32_t initial[8] = {
        0x6a09e667,0xbb67ae85,0x3c6ef372,0xa54ff53a,
        0x510e527f,0x9b05688c,0x1f83d9ab,0x5be0cd19
    };
    unsigned i;
    for (i = 0; i < 8; ++i) s->state[i] = initial[i];
    s->used = 0; s->bytes_lo = 0; s->bytes_hi = 0;
}

static void sha_add(Sha256 *s, const uint8_t *p, size_t n)
{
    size_t i;
    uint32_t previous=s->bytes_lo;
    s->bytes_lo+=(uint32_t)n;
    s->bytes_hi+=(s->bytes_lo<previous?1u:0u);
#if SIZE_MAX > UINT32_MAX
    s->bytes_hi+=(uint32_t)(n>>32);
#endif
    for (i = 0; i < n; ++i) {
        s->block[s->used++] = p[i];
        if (s->used == 64) { sha_block(s); s->used = 0; }
    }
}

static void sha_finish(Sha256 *s, uint8_t digest[32])
{
    unsigned i;
    s->block[s->used++] = 0x80;
    if (s->used > 56) {
        while (s->used < 64) s->block[s->used++] = 0;
        sha_block(s); s->used = 0;
    }
    while (s->used < 56) s->block[s->used++] = 0;
    put32(s->block+56,(s->bytes_hi<<3)|(s->bytes_lo>>29));
    put32(s->block+60,s->bytes_lo<<3);
    sha_block(s);
    for (i = 0; i < 8; ++i) put32(digest + 4u*i, s->state[i]);
}

void gxr2_sha256(const uint8_t *bytes, size_t length, uint8_t digest[32])
{
    Sha256 s;
    sha_init(&s); sha_add(&s, bytes, length); sha_finish(&s, digest);
}

