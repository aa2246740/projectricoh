/* Execute decoded instructions from the final integrated M32R engine. */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef struct {uint32_t base,size;uint8_t *bytes;} Region;
static Region regions[64];static unsigned region_count;
static uint32_t r[16],cf,pc,next_pc,min_sp;
static uint64_t steps,total_steps,acc;
static const uint32_t initial_sp=0x30010000,return_pc=0x3fff0000;
static uint8_t scratch[0x20000];

static void fail(const char *reason)
{fprintf(stderr,"target check failed: %s pc=%08x steps=%llu\n",reason,pc,(unsigned long long)steps);exit(1);}

static uint8_t *address(uint32_t at,unsigned n,int writing)
{
    unsigned i;(void)writing;
    if(at>=0x30000000 && at-0x30000000<=sizeof(scratch)-n)return scratch+at-0x30000000;
    for(i=region_count;i;i--){Region *region=&regions[i-1];
        if(at>=region->base && at-region->base<=region->size && n<=region->size-(at-region->base))
            return region->bytes+at-region->base;
    }
    fail("memory range");return NULL;
}
static uint32_t read_mem(uint32_t at,unsigned n)
{
    uint8_t *p=address(at,n,0);uint32_t value=0;unsigned i;
    if(n==4 && (at&3))fail("word alignment");
    for(i=0;i<n;i++)value=(value<<8)|p[i];return value;
}
static void write_mem(uint32_t at,uint32_t value,unsigned n)
{
    uint8_t *p=address(at,n,1);unsigned i;
    if(n==4 && (at&3))fail("word alignment");
    for(i=0;i<n;i++){p[n-1-i]=(uint8_t)value;value>>=8;}
}
static void add_carry(unsigned d,uint32_t value)
{uint64_t sum=(uint64_t)r[d]+value+cf;r[d]=(uint32_t)sum;cf=(uint32_t)(sum>>32);}
static void sub_carry(unsigned d,uint32_t value)
{uint64_t amount=(uint64_t)value+cf;cf=(uint64_t)r[d]<amount;r[d]-=(uint32_t)amount;}

static void execute(uint32_t entry)
{
    pc=entry;steps=0;min_sp=r[15];
    while(pc!=return_pc){
        if(++steps>3000000)fail("step budget");next_pc=pc+4;
        switch(pc){
#include "program.inc"
        default:fail("instruction address");
        }
        if(r[15]<min_sp)min_sp=r[15];pc=next_pc;
    }
    total_steps+=steps;
}

static void load_regions(const char *directory)
{
    char path[4096],name[256];unsigned base,size;FILE *file,*part;
    snprintf(path,sizeof(path),"%s/regions.txt",directory);file=fopen(path,"r");if(!file)fail("regions file");
    while(fscanf(file,"%x %u %255s",&base,&size,name)==3){
        Region *region;if(region_count>=64)fail("region count");region=&regions[region_count++];
        region->base=base;region->size=size;region->bytes=malloc(size);if(!region->bytes)fail("host memory");
        snprintf(path,sizeof(path),"%s/%s",directory,name);part=fopen(path,"rb");if(!part)fail("region file");
        if(fread(region->bytes,1,size,part)!=size)fail("region length");fclose(part);
    }
    fclose(file);
}

int main(int argc,char **argv)
{
    FILE *file;uint8_t record[580],*immutable;unsigned count=0,maximum=0,i,slot;uint32_t entry,image,length;
    if(argc!=6)fail("arguments");load_regions(argv[1]);entry=(uint32_t)strtoul(argv[3],0,0);
    image=(uint32_t)strtoul(argv[4],0,0);length=(uint32_t)strtoul(argv[5],0,0);
    immutable=malloc(length);if(!immutable)fail("host memory");memcpy(immutable,address(image,length,0),length);
    file=fopen(argv[2],"rb");if(!file)fail("cases file");
    while(fread(record,1,sizeof(record),file)==sizeof(record)){
        memset(scratch,0x5a,sizeof(scratch));
        for(i=0;i<16;i++)r[i]=0x12340000+i;
        slot=(uint32_t)record[4]<<24|(uint32_t)record[5]<<16|(uint32_t)record[6]<<8|record[7];
        memcpy(scratch+0x100,record+8,20);memset(scratch+0x1000,0xa5,552);
        cf=0;acc=0;r[0]=slot;r[1]=0x30000100;r[2]=0x30001000;r[14]=return_pc;r[15]=initial_sp;
        execute(entry);
        if(r[0]){fprintf(stderr,"case=%u status=%u\n",count,r[0]);fail("return value");}
        if(memcmp(scratch+0x1000,record+28,552)){
            for(i=0;i<552;i++)if(scratch[0x1000+i]!=record[28+i])break;
            fprintf(stderr,"case=%u byte=%u\n",count,i);fail("output bytes");
        }
        if(memcmp(scratch+0x100,record+8,20))fail("input vector");
        if(memcmp(immutable,address(image,length,0),length))fail("immutable DAT");
        if(scratch[0xff]!=0x5a||scratch[0x114]!=0x5a||scratch[0xfff]!=0x5a||scratch[0x1228]!=0x5a)fail("buffer limits");
        if(r[15]!=initial_sp)fail("stack restore");
        for(i=8;i<=13;i++)if(r[i]!=0x12340000+i)fail("saved register");
        if(initial_sp-min_sp>maximum)maximum=initial_sp-min_sp;count++;
    }
    if(!feof(file))fail("case read");fclose(file);
    printf("{\"cases\":%u,\"maximum_stack_bytes\":%u,\"instruction_steps\":%llu}\n",count,maximum,(unsigned long long)total_steps);
    return 0;
}
