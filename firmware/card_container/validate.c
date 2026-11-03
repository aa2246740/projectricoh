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

static int load_trust(const char *path, GxrceTrust *trust)
{
    uint8_t b[220];
    size_t n;
    unsigned i;
    if (!read_file(path,b,sizeof(b),&n) || n != sizeof(b) || memcmp(b,"GXTRUST1",8)) return 0;
    memcpy(trust->body_sha256,b+8,32);
    memcpy(trust->resident_build_id,b+40,32);
    memcpy(trust->resident_abi_id,b+72,16);
    for (i=0; i<3; ++i) {
        memcpy(trust->modules[i].unit.name,b+88+44*i,8);
        trust->modules[i].unit.main_version=be16(b+96+44*i);
        trust->modules[i].unit.cmp_version=be16(b+98+44*i);
        memcpy(trust->modules[i].stock_pin,b+100+44*i,32);
    }
    return 1;
}

int main(int argc, char **argv)
{
    GxrceTrust trust;
    GxrceUnit unit;
    GxrceView view,installed;
    GxrceStatus status;
    uint8_t *bytes,*old=NULL;
    size_t length,old_length;
    unsigned options=0;
    int i,exit_code=2;
    const char *installed_path=NULL;
    if (argc < 4 || strlen(argv[3]) != 7) {
        fprintf(stderr,"usage: validate FILE TRUST UNIT [--host-only] [--installed FILE]\n");
        return 2;
    }
    for (i=4; i<argc; ++i) {
        if (!strcmp(argv[i],"--host-only")) options=GXRCE_HOST_ONLY;
        else if (!strcmp(argv[i],"--installed") && i+1<argc) installed_path=argv[++i];
        else { fprintf(stderr,"bad option\n"); return 2; }
    }
    if (!load_trust(argv[2],&trust)) { fprintf(stderr,"TRUST_IO\n"); return 2; }
    memcpy(unit.name,argv[3],8); unit.main_version=0x0151; unit.cmp_version=0;
    bytes=malloc(GXRCE_MAX_FILE+1);
    if (!bytes) return 2;
    if (!read_file(argv[1],bytes,GXRCE_MAX_FILE+1,&length)) {
        fprintf(stderr,"FILE_IO_OR_OVERSIZE\n"); goto done;
    }
    status=gxrce_validate(bytes,length,&trust,&unit,options,&view);
    if (status != GXRCE_OK) { fprintf(stderr,"%s\n",gxrce_status_name(status)); goto done; }
    if (installed_path) {
        GxrceUpdate action;
        old=malloc(GXRCE_MAX_FILE+1);
        if (!old || !read_file(installed_path,old,GXRCE_MAX_FILE+1,&old_length)) {
            fprintf(stderr,"INSTALLED_IO\n"); goto done;
        }
        status=gxrce_validate(old,old_length,&trust,&unit,options,&installed);
        if (status != GXRCE_OK) { fprintf(stderr,"INSTALLED_%s\n",gxrce_status_name(status)); goto done; }
        action=gxrce_update_decide(&view,&installed);
        if (action == GXRCE_UPDATE_CONFLICT) { fprintf(stderr,"BUILD_CONFLICT\n"); goto done; }
        printf("update=%s ",action == GXRCE_UPDATE_INSTALL ? "install" : "keep");
    }
    printf("OK build=%u bytes=%u module=%u executable=%u\n",
           view.build_number,view.length,view.selected_module,view.executable);
    exit_code=0;
done:
    free(old); free(bytes);
    return exit_code;
}
