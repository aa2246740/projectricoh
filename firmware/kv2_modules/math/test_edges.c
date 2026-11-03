#include "kv_math.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

static struct {
    uint8_t before[32];
    KvWork area;
    uint8_t after[32];
} guard;

static void check_guard(void)
{
    unsigned i;
    for(i=0;i<32;i++)assert(guard.before[i]==0x5a && guard.after[i]==0x5a);
}

int main(int argc,char **argv)
{
    FILE *file;
    uint8_t stock[552],base[552],expected[552],same[552],bad[552],buffer[2208],before[2208];
    KvRequest req={100,{0},0,0};KvStats stats,expected_stats,same_stats;
    unsigned count=0,i,j,k;int shift,status;
    static const int shifts[]={-551,-128,-1,0,1,128,551};
    assert(argc==2);file=fopen(argv[1],"rb");assert(file);
    while(fread(stock,1,552,file)==552){
        assert(fread(base,1,552,file)==552);
        memset(&guard,0x5a,sizeof(guard));
        for(k=0;k<3;k++){
            memset(&req,0,sizeof(req));req.amount=k==0?100:k==1?0:73;
            if(k==2){req.dose[0]=1200;req.dose[1]=-2500;req.dose[2]=700;
                req.dose[3]=900;req.dose[4]=2400;req.dose[5]=300;
                req.dose[6]=-600;req.dose[7]=800;req.dose[8]=1200;}
            assert(kv_apply_work(stock,base,&req,expected,&expected_stats,&guard.area)==0);
            assert(kv_apply_work(stock,stock,&req,same,&same_stats,&guard.area)==0);
            for(i=0;i<3;i++)for(j=0;j<sizeof(shifts)/sizeof(shifts[0]);j++){
                shift=shifts[j];memset(buffer,0x5a,sizeof(buffer));
                memcpy(buffer+700,i==1?base:stock,552);memcpy(before,buffer,sizeof(buffer));
                status=kv_apply_work(i==1?stock:buffer+700,i?buffer+700:base,&req,
                                     buffer+700+shift,&stats,&guard.area);
                assert(status==0 && !memcmp(buffer+700+shift,i==2?same:expected,552));
                assert(!memcmp(&stats,i==2?&same_stats:&expected_stats,sizeof(stats)));
                assert(!memcmp(buffer,before,(size_t)(700+shift)));
                assert(!memcmp(buffer+1252+shift,before+1252+shift,(size_t)(956-shift)));
                check_guard();count++;
            }
            memcpy(guard.area.base,base,552);guard.area.request=req;
            assert(kv_apply_work(stock,guard.area.base,&guard.area.request,
                                 buffer,&stats,&guard.area)==0);
            assert(!memcmp(buffer,expected,552));
            assert(!memcmp(&stats,&expected_stats,sizeof(stats)));check_guard();count++;
        }
        req.amount=100;memset(req.dose,0,sizeof(req.dose));
        for(i=0;i<6;i++){
            memset(buffer,0xa5,552);memset(&stats,0x67,sizeof(stats));
            status=kv_apply_work(i==0?NULL:stock,i==1?NULL:base,i==2?NULL:&req,
                                 i==3?NULL:buffer,i==4?NULL:&stats,i==5?NULL:&guard.area);
            assert(status==-1);for(j=0;j<552;j++)assert(buffer[j]==0xa5);
            for(j=0;j<sizeof(stats);j++)assert(((uint8_t *)&stats)[j]==0x67);
            check_guard();count++;
        }
        for(i=0;i<23;i++){
            KvRequest bad_req=req;
            if(i<20){int param=(int)i/2;int cap=param==0||param==1||param==2||param==4?16384:4096;
                bad_req.dose[param]=(i&1)?cap+1:-cap-1;}
            else if(i==20)bad_req.amount=INT32_MIN;
            else if(i==21)bad_req.dose[3]=-1;
            else bad_req.wb_method=INT32_MAX;
            memset(buffer,0xa5,552);memset(&stats,0x67,sizeof(stats));
            assert(kv_apply_work(stock,base,&bad_req,buffer,&stats,&guard.area)==-1);
            for(j=0;j<552;j++)assert(buffer[j]==0xa5);
            for(j=0;j<sizeof(stats);j++)assert(((uint8_t *)&stats)[j]==0x67);
            check_guard();count++;
        }
        memcpy(bad,base,552);bad[1]|=1;memset(bad+216,0,6);
        req.dose[5]=4096;memset(buffer,0xa5,552);memset(&stats,0x67,sizeof(stats));
        assert(kv_apply_work(stock,bad,&req,buffer,&stats,&guard.area)==-2);
        for(j=0;j<552;j++)assert(buffer[j]==0xa5);
        for(j=0;j<sizeof(stats);j++)assert(((uint8_t *)&stats)[j]==0x67);
        check_guard();count++;
    }
    assert(feof(file));fclose(file);
    printf("PASS edge cases %u\n",count);return 0;
}
