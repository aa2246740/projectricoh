#include "gxrce.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static uint16_t be16(const uint8_t *p)
{ return (uint16_t)((uint16_t)p[0] << 8 | p[1]); }

static int read_file(const char *path, uint8_t *bytes, size_t capacity, size_t *length)
{
    FILE *f = fopen(path,"rb");
    size_t n;
    int extra,failed;
    if (!f) return 0;
    n=fread(bytes,1,capacity,f);
    extra=fgetc(f);
    failed=ferror(f);
    if (fclose(f) != 0) failed=1;
    if (extra != EOF || failed) return 0;
    *length=n;
    return 1;
}

static int load_trust(const char *path, Gxr2Trust *trust)
{
    uint8_t b[232];
    size_t n;
    unsigned i;
    if (!read_file(path,b,sizeof(b),&n) || n != sizeof(b) || memcmp(b,"GXTRUST2",8)) return 0;
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
    return 1;
}

int main(int argc, char **argv)
{
    Gxr2Trust trust;
    Gxr2Unit unit;
    Gxr2View view,installed;
    Gxr2Status status;
    uint8_t *bytes,*old=NULL;
    size_t length,old_length;
    unsigned options=0;
    int gate_only=0;
    int i,exit_code=2;
    const char *installed_path=NULL;
    if (argc < 4 || strlen(argv[3]) != 7) {
        fprintf(stderr,"usage: validate FILE TRUST UNIT [--host-only] [--gate | --installed FILE]\n");
        return 2;
    }
    for (i=4; i<argc; ++i) {
        if (!strcmp(argv[i],"--host-only")) options=GXR2_HOST_ONLY;
        else if (!strcmp(argv[i],"--gate")) gate_only=1;
        else if (!strcmp(argv[i],"--installed") && i+1<argc) installed_path=argv[++i];
        else { fprintf(stderr,"bad option\n"); return 2; }
    }
    if (gate_only && installed_path) { fprintf(stderr,"GATE_CANNOT_AUTHORIZE_UPDATE\n"); return 2; }
    if (!load_trust(argv[2],&trust)) { fprintf(stderr,"TRUST_IO\n"); return 2; }
    memcpy(unit.name,argv[3],8); unit.main_version=0x0151; unit.cmp_version=0;
    bytes=malloc(GXR2_MAX_FILE+1);
    if (!bytes) return 2;
    if (!read_file(argv[1],bytes,GXR2_MAX_FILE+1,&length)) {
        fprintf(stderr,"FILE_IO_OR_OVERSIZE\n"); goto done;
    }
    status=(gate_only?gxr2_gate_validate:gxr2_validate)(bytes,length,&trust,&unit,options,&view);
    if (status != GXR2_OK) { fprintf(stderr,"%s\n",gxr2_status_name(status)); goto done; }
    if (installed_path) {
        int action;
        old=malloc(GXR2_MAX_FILE+1);
        if (!old || !read_file(installed_path,old,GXR2_MAX_FILE+1,&old_length)) {
            fprintf(stderr,"INSTALLED_IO\n"); goto done;
        }
        status=gxr2_validate(old,old_length,&trust,&unit,options,&installed);
        if (status != GXR2_OK) { fprintf(stderr,"INSTALLED_%s\n",gxr2_status_name(status)); goto done; }
        action=gxr2_update_decide(&view,&installed);
        if (action == GXR2_CONFLICT) { fprintf(stderr,"BUILD_CONFLICT\n"); goto done; }
        printf("update=%s ",action == GXR2_INSTALL ? "install" : "keep");
    }
    printf("OK build=%u bytes=%u module=%u executable=%u semantic=%u\n",
           view.build_number,view.length,view.selected_module,view.executable,view.semantic);
    exit_code=0;
done:
    free(old); free(bytes);
    return exit_code;
}
