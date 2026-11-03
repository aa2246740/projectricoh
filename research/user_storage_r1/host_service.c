/* Host boundary probe. The included storage() is copied verbatim by verify.py. */
#include "storage_prefix.inc"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static RvSession session;
static unsigned char memory[0x800000];
static unsigned creates,writes,renames,deletes,opens,closes;
int rv_equal(const void *p,const void *q,uint32_t n){return !memcmp(p,q,n);}
RvSession *rv_session(RvRoot *r){(void)r;return &session;}
int rv_range(RvRoot *r,uint32_t t,uint32_t a,uint32_t n)
{(void)r;(void)t;return a>=0x20000000u&&a+n<=0x20800000u;}
void *rv_host_address(uint32_t a)
{if(a<0x20000000u||a>=0x20800000u)abort();return memory+a-0x20000000u;}
int32_t rv_native_context(void){return 0;}
int32_t rv_native_sd_id(void *b){uint32_t *p=b;p[0]=1;p[1]=p[2]=p[3]=0;return 0;}
int32_t rv_native_open(const char *p,uint32_t f){(void)p;(void)f;++opens;return -1;}
int32_t rv_native_close(int32_t f){(void)f;++closes;return 0;}
int32_t rv_native_create(const char *p,uint32_t f){(void)p;(void)f;++creates;return 7;}
int32_t rv_native_write(int32_t f,const void *p,uint32_t n){(void)f;(void)p;++writes;return (int32_t)n;}
int32_t rv_native_read(int32_t f,void *p,uint32_t n){(void)f;(void)p;(void)n;return 0;}
int32_t rv_native_rename(const char *p,const char *q){(void)p;(void)q;++renames;return 0;}
int32_t rv_native_delete(const char *p){(void)p;++deletes;return 0;}
int32_t es_storage_mark(RvRoot *r,const RvRequest *q,RvReply *p)
{(void)r;(void)q;(void)p;return RV_UNSUPPORTED;}
#define CHECK(x) do{if(!(x)){fprintf(stderr,"line %d: %s\n",__LINE__,#x);return 1;}}while(0)

int main(void)
{
    RvRoot root={0};RvRequest q={0};RvReply reply={0};int32_t result;
    root.state=RV_READY;root.inflight=1;root.epoch[RV_IO_E]=1;root.next_token=10;
    session.capabilities=RV_READ_CAPS|CAP_UI|CAP_S|CAP_W;
    CHECK(session.capabilities==0xe7fffu&&!(session.capabilities&CAP_FILE_WRITE));
    q.args[0]=1;q.args[2]=2;q.args[3]=1;q.args[5]=4;q.args[8]=64;
    CHECK(storage(&root,3,&q,&reply)==RV_CAPABILITY&&!creates);
    q.args[8]=0;q.args[9]=2;q.args[10]=3;
    CHECK(storage(&root,7,&q,&reply)==RV_CAPABILITY&&!renames);
    q.args[9]=q.args[10]=0;
    CHECK(storage(&root,8,&q,&reply)==RV_CAPABILITY&&!deletes);
    q.args[1]=9;q.args[2]=q.args[3]=q.args[5]=0;
    q.args[6]=0x20610000;q.args[7]=32;
    session.files[0]=(RvFileToken){9,7,1,0};session.file_object[0]=0x02010002;
    session.file_limit[0]=256;
    CHECK(storage(&root,5,&q,&reply)==RV_RANGE&&!writes);
    session.files[0].token=0;
    memset(&q,0,sizeof(q));q.args[0]=1;q.args[2]=2;q.args[3]=1;q.args[5]=4;q.args[8]=64;
    session.capabilities|=CAP_FILE_WRITE;
    CHECK(session.capabilities==0xf7fffu);
    result=storage(&root,3,&q,&reply);
    CHECK(result==RV_OK&&creates==1&&reply.token&&session.files[0].mode==1);
    printf("PASS actual DAT storage prefix: caps E7FFF create=-12 rename=-12 delete=-12 read_token_write=-10; caps F7FFF create=0 native_create_calls=%u\n",creates);
    memset(&q,0,sizeof(q));q.args[0]=1;q.args[2]=4;q.args[3]=1;q.args[5]=4;q.args[8]=16384;
    CHECK(storage(&root,3,&q,&reply)==RV_ARGUMENT&&creates==1);
    puts("PASS new user object kind=4 unsupported: capability bit alone does not implement fixed-file storage");
    return 0;
}
