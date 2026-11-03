/* Verify service admission during the single, validated bootstrap call. */
#define main host_review_original_main
#define rv_invoke review_standard_invoke
#include "host_review.c"
#undef rv_invoke
#undef main

static int32_t read_result,write_result;
static uint32_t bootstrap_caps,bootstrap_state;
int32_t rv_invoke(uint32_t address,const RvApi *api,uint32_t lease,const RvRequest *q,RvReply *p)
{
    RvSession *s=rv_session(&root);
    if(address==s->image_address+256){
        RvRequest service=*q;RvReply reply;
        bootstrap_caps=s->capabilities;bootstrap_state=root.state;
        snapshot(&service);memset(service.args+8,0,6*sizeof(uint32_t));
        s->rpc_token=17;service.args[1]=17;service.args[8]=123;
        read_result=rv_service(&root,RV_RPC8,2,&service,&reply);
        write_result=rv_service(&root,RV_RPC8,3,&service,&reply);
    }
    return review_standard_invoke(address,api,lease,q,p);
}
int main(void)
{
    reset();load();
    REQUIRE(bootstrap_state==RV_VALIDATED && bootstrap_caps==RV_READ_CAPS);
    REQUIRE(read_result==RV_OK && write_result==RV_CAPABILITY && !native_writes);
    printf("{\"state_during_bootstrap\":%u,\"capabilities\":%u,\"rpc_read_result\":%d,\"rpc_write_result\":%d,\"native_writes\":%u}\n",bootstrap_state,bootstrap_caps,read_result,write_result,native_writes);
    return 0;
}
