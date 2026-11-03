#include "probe.h"
/* Read-only and fixed. No special T page or dynamically supplied address. */
static const struct {uint32_t address,bytes;} ranges[]={
    {0x2012c0f4,48},{0x2012d0b4,8},{0x2012d0c0,28},{0x2012d1f8,2},
    {0x20383e68,12},{0x20142ab4,4},{0x20142ab8,48},{0x20142b48,32},
    {0x20142b68,32},{0x2012c600,4},{0x20142b14,4},{0x2012d1a0,14},
    {0x2012d1f4,10},{0x2012d0dc,14}
};
static int rpc(ProbeState *s,unsigned op,uint32_t value,uint32_t token,RvReply *reply)
{
    RvRequest q=s->request;unsigned i;
    for(i=8;i<14;++i)q.args[i]=0;
    q.args[1]=token;q.args[8]=value;
    return s->api->call(RV_RPC8,op,&q,reply)==RV_OK&&reply->status==RV_OK;
}
int probe_baseline(ProbeState *s,int capture)
{
    RvReply reply;uint32_t token=0,index=0,i,j,word;int result=1;
    if(!s->is50||(!capture&&!s->baseline_valid))return 0;
    if(!rpc(s,1,0,0,&reply))return 0;
    token=reply.token;
    for(i=0;result&&i<sizeof(ranges)/sizeof(ranges[0]);++i){
        if(!rpc(s,4,ranges[i].address>>16,token,&reply)){result=0;break;}
        for(j=0;j<ranges[i].bytes;j+=2){
            if(!rpc(s,2,(ranges[i].address+j)&65535u,token,&reply)||reply.native_result<0||reply.native_result>65535){result=0;break;}
            word=(uint32_t)reply.native_result;
            if(index+2>BASE_BYTES){result=0;break;}
            if(capture){s->baseline[index]=(uint8_t)(word>>8);s->baseline[index+1]=(uint8_t)word;}
            else if(s->baseline[index]!=(uint8_t)(word>>8)||s->baseline[index+1]!=(uint8_t)word)result=-1;
            index+=2;
        }
    }
    if(!rpc(s,5,0,token,&reply))result=0;
    if(index!=BASE_BYTES)result=0;
    if(capture)s->baseline_valid=result==1;
    s->baseline_status=result==1?1:result==-1?2:3;
    return result==1;
}
