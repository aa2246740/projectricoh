/* Host-side executor for decoded standalone M32R instructions. */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static uint32_t r[16],cf,pc,next_pc,min_sp;
static uint64_t steps;
static uint8_t code[32768],ram[65536];
static size_t code_size;

static void fail(const char *reason)
{
    fprintf(stderr,"target check failed: %s pc=%08x steps=%llu\n",reason,pc,
            (unsigned long long)steps);
    exit(1);
}

static uint8_t *address(uint32_t at,unsigned n,int writing)
{
    if(at>=0x200000 && at-0x200000<=sizeof(ram)-n)return ram+at-0x200000;
    if(!writing && at>=0x100000 && at-0x100000+n<=code_size)return code+at-0x100000;
    fail("memory range");return NULL;
}

static uint32_t read_mem(uint32_t at,unsigned n)
{
    uint8_t *p=address(at,n,0);uint32_t value=0;unsigned i;
    if(n==4 && (at&3))fail("word alignment");
    for(i=0;i<n;i++)value=(value<<8)|p[i];
    return value;
}

static void write_mem(uint32_t at,uint32_t value,unsigned n)
{
    uint8_t *p=address(at,n,1);unsigned i;
    if(n==4 && (at&3))fail("word alignment");
    for(i=0;i<n;i++){p[n-1-i]=(uint8_t)value;value>>=8;}
}

static void add_carry(unsigned d,uint32_t value)
{
    uint64_t sum=(uint64_t)r[d]+value+cf;r[d]=(uint32_t)sum;cf=(uint32_t)(sum>>32);
}

static void sub_carry(unsigned d,uint32_t value)
{
    uint64_t sub=(uint64_t)value+cf;cf=(uint64_t)r[d]<sub;r[d]-=(uint32_t)sub;
}

static void execute(uint32_t entry)
{
    pc=entry;steps=0;min_sp=r[15];
    while(pc!=0x300000){
        if(++steps>2000000)fail("step budget");
        next_pc=pc+4;
        switch(pc){
#include "program.inc"
        default:fail("instruction address");
        }
        if(r[15]<min_sp)min_sp=r[15];
        pc=next_pc;
    }
}

static void reset(void)
{
    unsigned i;memset(ram,0x5a,sizeof(ram));
    for(i=0;i<16;i++)r[i]=0x12340000+i;
    cf=0;r[14]=0x300000;r[15]=0x20f000;
}

static void abi_check(void)
{
    unsigned i;
    if(r[15]!=0x20f000)fail("stack restore");
    for(i=8;i<=13;i++)if(r[i]!=0x12340000+i)fail("saved register");
}

static void run_parity(const char *path,uint32_t entry)
{
    FILE *file=fopen(path,"rb");uint8_t record[1740];
    unsigned long count=0;uint32_t maximum=0;uint64_t total=0;
    if(!file)fail("case file");
    while(fread(record,1,sizeof(record),file)==sizeof(record)){
        reset();memcpy(ram,record,552);memcpy(ram+0x300,record+552,552);
        memcpy(ram+0x600,record+1104,52);memset(ram+0x700,0xa5,552);
        {unsigned i;for(i=0;i<7;i++)write_mem(0x200a00+4*i,UINT32_C(0xfffffcf7),4);}
        r[0]=0x200000;r[1]=0x200300;r[2]=0x200600;r[3]=0x200700;
        write_mem(r[15],0x200a00,4);write_mem(r[15]+4,0x201000,4);
        execute(entry);abi_check();
        if(r[0]!=((uint32_t)record[1156]<<24|(uint32_t)record[1157]<<16|
                 (uint32_t)record[1158]<<8|record[1159]))fail("return value");
        if(memcmp(ram+0x700,record+1188,552)){
            fprintf(stderr,"case=%lu\n",count);fail("output bytes");
        }
        if(memcmp(ram+0xa00,record+1160,28))fail("stats bytes");
        if(memcmp(ram,record,552) || memcmp(ram+0x300,record+552,552))fail("input bytes");
        if(0x20f000-min_sp>maximum)maximum=0x20f000-min_sp;
        total+=steps;count++;
    }
    if(!feof(file))fail("case read");fclose(file);
    printf("{\"cases\":%lu,\"maximum_stack\":%u,\"instructions\":%llu}\n",
           count,maximum,(unsigned long long)total);
}

static void run_i64(const char *path,uint32_t multiply,uint32_t divide)
{
    FILE *file=fopen(path,"rb");uint8_t record[32],actual[8];
    unsigned long count=0;unsigned i,j;uint32_t entries[2]={multiply,divide};
    uint32_t maximum=0;
    if(!file)fail("integer case file");
    while(fread(record,1,sizeof(record),file)==sizeof(record)){
        for(j=0;j<2;j++){
            reset();memcpy(ram,record,16);
            for(i=0;i<4;i++)r[i]=read_mem(0x200000+4*i,4);
            execute(entries[j]);abi_check();
            for(i=0;i<8;i++)actual[i]=(uint8_t)(r[i/4]>>(24-8*(i%4)));
            if(memcmp(actual,record+16+8*j,8))fail("integer value");
            if(0x20f000-min_sp>maximum)maximum=0x20f000-min_sp;
        }
        count++;
    }
    if(!feof(file))fail("integer case read");fclose(file);
    printf("{\"i64_pairs\":%lu,\"maximum_stack\":%u}\n",count,maximum);
}

int main(int argc,char **argv)
{
    FILE *file;
    if(argc!=5 && argc!=6)return 2;
    file=fopen(argv[1],"rb");if(!file)return 2;
    code_size=fread(code,1,sizeof(code),file);fclose(file);
    if(!strcmp(argv[2],"parity"))run_parity(argv[3],(uint32_t)strtoul(argv[4],NULL,0));
    else if(!strcmp(argv[2],"i64") && argc==6)
        run_i64(argv[3],(uint32_t)strtoul(argv[4],NULL,0),(uint32_t)strtoul(argv[5],NULL,0));
    else return 2;
    return 0;
}
