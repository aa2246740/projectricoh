#include "kv_math.h"
#include <assert.h>
#include <stdio.h>

static uint64_t read64(const uint8_t *bytes)
{
    uint64_t value=0;unsigned i;
    for(i=0;i<8;i++)value=(value<<8)|bytes[i];
    return value;
}

int main(int argc,char **argv)
{
    FILE *file;uint8_t record[32];unsigned count=0;
    assert(argc==2);file=fopen(argv[1],"rb");assert(file);
    while(fread(record,1,sizeof(record),file)==sizeof(record)){
        int64_t a=(int64_t)read64(record),b=(int64_t)read64(record+8);
        assert((uint64_t)__muldi3(a,b)==read64(record+16));
        assert((uint64_t)__divdi3(a,b)==read64(record+24));count++;
    }
    assert(feof(file));fclose(file);assert(count==100121);
    printf("PASS integer pairs %u\n",count);return 0;
}
