#include "gxrce.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static int failures;

static void check(int condition, const char *message)
{
    if (!condition) { fprintf(stderr,"FAIL %s\n",message); ++failures; }
}

static uint16_t be16(const uint8_t *p)
{ return (uint16_t)((uint16_t)p[0] << 8 | p[1]); }

static void trust_decode(const uint8_t *b, Gxr2Trust *trust)
{
    unsigned i;
    memcpy(trust->body_sha256,b+8,32);
    memcpy(trust->resident_build_id,b+40,32);
    memcpy(trust->resident_abi_id,b+72,16);
    for (i=0; i<3; ++i) {
        memcpy(trust->modules[i].unit.name,b+88+48*i,8);
        trust->modules[i].unit.main_version=be16(b+96+48*i);
        trust->modules[i].unit.cmp_version=be16(b+98+48*i);
        trust->modules[i].stock_crc32=(uint32_t)b[100+48*i]<<24 | (uint32_t)b[101+48*i]<<16 | (uint32_t)b[102+48*i]<<8 | b[103+48*i];
        memcpy(trust->modules[i].stock_sha256,b+104+48*i,32);
    }
}

static int digest_is(const uint8_t *p, size_t n, const char *hex)
{
    static const char digits[]="0123456789abcdef";
    uint8_t digest[32];
    unsigned i;
    gxr2_sha256(p,n,digest);
    for (i=0; i<32; ++i)
        if (digits[digest[i] >> 4] != hex[2*i] || digits[digest[i] & 15u] != hex[2*i+1]) return 0;
    return 1;
}

static void hash_tests(void)
{
    uint8_t message[1000];
    memset(message,'a',sizeof(message));
    check(gxr2_crc32((const uint8_t *)"123456789",9) == UINT32_C(0xcbf43926),"CRC check vector");
    check(gxr2_crc32(message,0) == 0,"empty CRC is legal");
    check(digest_is(message,0,"e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"),"SHA empty");
    check(digest_is((const uint8_t *)"abc",3,"ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"),"SHA abc");
    check(digest_is(message,55,"9f4390f8d30c2dd92ec9f095b65e2b9ae9b0a925a5258e241c9f1e910f734318"),"SHA 55");
    check(digest_is(message,56,"b35439a4ac6f0948b6d6f9e3c6af0f5f590ce20f1bde7090ef7970686ec6738a"),"SHA 56");
    check(digest_is(message,64,"ffe054fe7ae0cb6dc65c3af9b61d5209f439851db43d0ba5997337df154668eb"),"SHA 64");
    check(digest_is(message,1000,"41edece42d63e8d9bf515a9ba6932e1c20cbc9f5a5d134645adb5db1b9737ea3"),"SHA multi-block");
}

int test_gxts(const Gxr2View *);

int main(int argc, char **argv)
{
    FILE *f;
    uint8_t *bytes,*copy,*small,trust_bytes[232];
    size_t n,length;
    uint32_t rng=UINT32_C(0x6c712d39);
    Gxr2Trust trust;
    Gxr2Unit unit;
    Gxr2View output,sentinel;
    Gxr2Status status;
    unsigned i;
    if (argc != 3 && argc != 4) return 2;
    bytes=malloc(GXR2_MAX_FILE+1); copy=malloc(GXR2_MAX_FILE+2);
    if (!bytes || !copy) return 2;
    f=fopen(argv[1],"rb"); if (!f) return 2;
    length=fread(bytes,1,GXR2_MAX_FILE+1,f);
    if (ferror(f) || fclose(f) || length < 256 || length > GXR2_MAX_FILE) return 2;
    f=fopen(argv[2],"rb"); if (!f) return 2;
    n=fread(trust_bytes,1,sizeof(trust_bytes),f);
    if (ferror(f) || fclose(f) || n != sizeof(trust_bytes)) return 2;
    trust_decode(trust_bytes,&trust); unit=trust.modules[0].unit;
    hash_tests();
    check(gxr2_validate(bytes,length,&trust,&unit,GXR2_HOST_ONLY,&output) == GXR2_OK,"baseline validates");
    check(output.build_number == 1 && output.length == 7320 && !output.executable && output.selected_module == 0,
          "baseline literal view");
    check(gxr2_update_decide(&output,NULL) == GXR2_INSTALL,"missing installed package");
    failures+=test_gxts(&output);
    memset(&sentinel,0xa5,sizeof(sentinel));
    for (n=0; n<length; ++n) {
        small=malloc(n ? n : 1);
        if (!small) return 2;
        memcpy(small,bytes,n); output=sentinel;
        status=gxr2_validate(small,n,&trust,&unit,GXR2_HOST_ONLY,&output);
        check(status != GXR2_OK,"every exact allocation truncation rejected");
        check(gxr2_gate_validate(small,n,&trust,&unit,GXR2_HOST_ONLY,&output)!=GXR2_OK,"gate truncation rejected");
        check(memcmp(&output,&sentinel,sizeof(output)) == 0,"failure output unchanged");
        check(memcmp(small,bytes,n) == 0,"truncated input unchanged");
        free(small);
    }
    memcpy(copy+1,bytes,length);
    check(gxr2_validate(copy+1,length,&trust,&unit,GXR2_HOST_ONLY,&output) == GXR2_OK,"unaligned file input");
    check(memcmp(copy+1,bytes,length) == 0,"valid input unchanged");
    check(gxr2_validate(bytes,length,&trust,&unit,0,&output) == GXR2_PLACEHOLDER,"stub rejected by runtime");
    check(gxr2_validate(bytes,GXR2_MAX_FILE+1,&trust,&unit,GXR2_HOST_ONLY,&output) == GXR2_LENGTH,"oversize before access");
    check(gxr2_validate(NULL,length,&trust,&unit,GXR2_HOST_ONLY,&output) == GXR2_ARGUMENT,"null input");
    check(gxr2_validate(bytes,length,&trust,&unit,2,&output) == GXR2_ARGUMENT,"unknown caller options");
    unit.main_version=0x0150;
    check(gxr2_validate(bytes,length,&trust,&unit,GXR2_HOST_ONLY,&output) == GXR2_MODULE_ID,"runtime MAIN version");
    unit.main_version=0x0151; unit.cmp_version=1;
    check(gxr2_validate(bytes,length,&trust,&unit,GXR2_HOST_ONLY,&output) == GXR2_MODULE_ID,"runtime CmpVer");
    unit=trust.modules[0].unit;
    for (i=0; i<1024; ++i) {
        rng^=rng<<13; rng^=rng>>17; rng^=rng<<5;
        n=rng%length;
        bytes[n]^=0x80;
        output=sentinel;
        check(gxr2_validate(bytes,length,&trust,&unit,GXR2_HOST_ONLY,&output) != GXR2_OK,"single-bit corruption rejected");
        check(memcmp(&output,&sentinel,sizeof(output)) == 0,"corruption output unchanged");
        check(gxr2_gate_validate(bytes,length,&trust,&unit,GXR2_HOST_ONLY,&output)!=GXR2_OK,"gate corruption rejected");
        bytes[n]^=0x80;
    }
    if (argc == 4) {
        uint8_t daily[3600],expanded[448]; unsigned slot;
        f=fopen(argv[3],"rb"); if(!f) return 2;
        n=fread(daily,1,sizeof(daily),f); if(ferror(f) || fclose(f) || n!=3600) return 2;
        check(gxr2_validate(bytes,length,&trust,&unit,GXR2_HOST_ONLY,&output)==GXR2_OK,"baseline revalidation");
        for(slot=1;slot<=6;++slot) {
            unsigned di;
            check(gxr2_expand(&output,0,slot,expanded)==GXR2_OK,"expand 01-06");
            for(di=0;di<8 && daily[16+di*448]!=slot;++di) {}
            check(di<8 && memcmp(expanded,daily+16+di*448,448)==0,"expanded table exactly matches DEEPTBL 44a0ff9e");
        }
    }
    free(copy); free(bytes);
    printf("core failures=%d exact_truncations=%zu deterministic_corruptions=1024 hash_vectors=8\n",failures,length);
    return failures ? 1 : 0;
}
