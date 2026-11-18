#include "kv_math.h"
#include <stddef.h>



#if defined(__GNUC__)
#define KV_STAGE_FN __attribute__((noinline))
#else
#define KV_STAGE_FN
#endif

static void kv_copy(void *dst,const void *src,size_t n)
{uint8_t *d=dst;const uint8_t *s=src;size_t i;for(i=0;i<n;i++)d[i]=s[i];}
static void kv_zero(void *dst,size_t n)
{uint8_t *d=dst;size_t i;for(i=0;i<n;i++)d[i]=0;}
static int kv_compare(const void *a,const void *b,size_t n)
{const uint8_t *x=a,*y=b;size_t i;for(i=0;i<n;i++)if(x[i]!=y[i])return (int)x[i]-(int)y[i];return 0;}
static void kv_move(void *dst,const void *src,size_t n)
{uint8_t *d=dst;const uint8_t *s=src;size_t i;if((uintptr_t)d<(uintptr_t)s){for(i=0;i<n;i++)d[i]=s[i];}else if(d!=s){for(i=n;i>0;i--)d[i-1]=s[i-1];}}

static const uint16_t off[10]={20,82,115,216,284,346,379,412,456,518};
static const uint8_t len[10]={62,33,96,56,62,33,33,33,62,33};
static const int exp_q12[257]={4096,4277,4467,4664,4871,5087,5312,5547,5793,6049,6317,6597,6889,7194,7512,7845,8192,8555,8933,9329,9742,10173,10624,11094,11585,12098,12634,13193,13777,14387,15024,15689,16384,17109,17867,18658,19484,20347,21247,22188,23170,24196,25268,26386,27554,28774,30048,31379,32768,34219,35734,37316,38968,40693,42495,44376,46341,48393,50535,52773,55109,57549,60097,62757,65536,68438,71468,74632,77936,81386,84990,88752,92682,96785,101070,105545,110218,115098,120194,125515,131072,136875,142935,149263,155872,162773,169979,177505,185364,193571,202141,211090,220436,230195,240387,251030,262144,273750,285870,298527,311744,325546,339959,355010,370728,387141,404281,422180,440872,460391,480774,502060,524288,547500,571740,597053,623487,651091,679917,710020,741455,774282,808563,844361,881744,920782,961548,1004120,1048576,1095000,1143480,1194106,1246974,1302182,1359835,1420040,1482910,1548564,1617125,1688722,1763488,1841564,1923097,2008240,2097152,2190001,2286960,2388213,2493948,2604365,2719670,2840080,2965821,3097129,3234251,3377443,3526975,3683128,3846194,4016479,4194304,4380002,4573921,4776426,4987896,5208729,5439339,5680159,5931642,6194258,6468501,6754886,7053950,7366255,7692387,8032959,8388608,8760003,9147842,9552851,9975792,10417458,10878679,11360319,11863283,12388516,12937002,13509772,14107901,14732511,15384775,16065917,16777216,17520007,18295684,19105703,19951585,20834917,21757357,22720638,23726566,24777031,25874004,27019544,28215802,29465022,30769550,32131834,33554432,35040014,36591368,38211406,39903169,41669834,43514715,45441276,47453133,49554062,51748008,54039088,56431603,58930044,61539100,64263668,67108864,70080027,73182735,76422812,79806339,83339667,87029429,90882551,94906266,99108125,103496017,108078177,112863206,117860087,123078199,128527337,134217728,140160054,146365470,152845623,159612677,166679334,174058859,181765103,189812531,198216250,206992033,216156353,225726413,235720175,246156398,257054673,268435456};
static const uint16_t max_dose[10]={16384,16384,16384,4096,16384,4096,4096,4096,4096,4096};
static const uint16_t crc_at[9]={8,12,16,212,272,276,280,448,452};
static const uint16_t crc_off[9]={20,82,115,216,284,346,379,456,518};
static const uint8_t crc_len[9]={62,33,96,56,62,33,66,62,33};

static int32_t kv_round_div(int64_t n,int64_t d)
{ return (int32_t)(n>=0?(n+d/2)/d:-((-n+d/2)/d)); }
static int abs_i(int x){return x<0?-x:x;}
static int min_i(int a,int b){return a<b?a:b;}
static int max_i(int a,int b){return a>b?a:b;}
static int clip(int v,int lo,int hi,int32_t *count)
{int r=max_i(lo,min_i(hi,v));if(r!=v && count)(*count)++;return r;}
static int be16(const uint8_t *p){return (int)p[0]*256+p[1];}
static void put16(uint8_t *p,int v){p[0]=(uint8_t)(v>>8);p[1]=(uint8_t)v;}
static int decode(int v,int sign){return v&sign?-(v&(sign-1)):v&(sign-1);}
static int encode(int v,int sign){return v<0?sign|(-v):v;}
static void matrix_read(const uint8_t *b,int32_t w[28])
{int i;for(i=0;i<28;i++)w[i]=decode(be16(b+216+2*i),2048);}
static void matrix_store(uint8_t *b,const int32_t w[28])
{int i;for(i=0;i<28;i++)put16(b+216+2*i,encode(w[i],2048));b[1]|=1;}
static uint32_t crc32(const uint8_t *p,int n)
{uint32_t c=UINT32_MAX;int i,k;for(i=0;i<n;i++){c^=p[i];for(k=0;k<8;k++)c=(c>>1)^((0u-(c&1u))&UINT32_C(0xedb88320));}return ~c;}
static void checksum(uint8_t *b)
{int i;for(i=0;i<9;i++){uint32_t c=crc32(b+crc_off[i],crc_len[i]);uint8_t *p=b+crc_at[i];p[0]=(uint8_t)(c>>24);p[1]=(uint8_t)(c>>16);p[2]=(uint8_t)(c>>8);p[3]=(uint8_t)c;}}

static void effective(uint8_t *o,const uint8_t *b,const uint8_t *stock)
{kv_copy(o,b,KV_BYTES);if(!(b[1]&1))kv_copy(o+216,stock+216,56);if(!(b[1]&2)){kv_copy(o+379,b+82,33);kv_copy(o+412,b+82,33);}if(!(b[1]&16))kv_copy(o+284,stock+284,95);}

static int node(const uint8_t *a,int j){return j==0?0:j==32?4095:be16(a+2*(j-1));}
static int interp_q16(const uint8_t *a,const uint8_t *curve,int x)
{
    int right=1,left,lo,hi;
    if(x>=4095)return curve[32]*65536;
    while(node(a,right)<x)right++;
    left=right-1;lo=node(a,left);hi=node(a,right);
    return curve[left]*65536+kv_round_div((int64_t)(x-lo)*(curve[right]-curve[left])*65536,hi-lo);
}
static void limit_one(uint8_t *b,int aa,int bb,KvStats *st)
{int j,cap;for(j=1;j<33;j++){cap=b[bb+j-1]+node(b+aa,j)-node(b+aa,j-1);if(b[bb+j]>cap){b[bb+j]=(uint8_t)cap;st->slope_repairs++;}}}
static void limit_slopes(uint8_t *b,KvStats *st)
{limit_one(b,20,82,st);limit_one(b,456,518,st);if(b[1]&16)limit_one(b,284,346,st);if(b[1]&4){limit_one(b,20,379,st);limit_one(b,20,412,st);}}

static KV_STAGE_FN void blend(uint8_t *o,const uint8_t *stock,const uint8_t *base,int amount,KvStats *st,KvStage *stage)
{
    uint8_t *a=stage->blend[0],*b=stage->blend[1];int i,j,at,n,prev,v;
    if(amount==100){kv_copy(o,base,KV_BYTES);return;}
    if(amount==0 || !kv_compare(base,stock,KV_BYTES)){kv_copy(o,stock,KV_BYTES);return;}
    effective(a,stock,stock);effective(b,base,stock);kv_copy(o,base,KV_BYTES);
    o[1]=stock[1]|base[1];if(o[1]&4)put16(o+445,0);
    for(i=0;i<10;i++){
        at=off[i];n=len[i];prev=0;
        if((at==379 || at==412) && !(o[1]&2))continue;
        if(n==62){kv_copy(o+at,b+at,62);continue;}
        for(j=0;j<(n==56?28:n);j++){
            if(n==96){
                v=kv_round_div((int64_t)(100-amount)*decode(a[at+j],128)+(int64_t)amount*decode(b[at+j],128),100);
                o[at+j]=(uint8_t)encode(clip(v,-127,127,&st->clamps),128);
            } else if(n==56){
                int av=be16(a+at+2*j),bv=be16(b+at+2*j);
                if(j%14<9){int lim=j%14<3?2047:1279;v=kv_round_div((int64_t)(100-amount)*decode(av,2048)+(int64_t)amount*decode(bv,2048),100);v=encode(clip(v,-lim,lim,&st->clamps),2048);}
                else v=clip(kv_round_div((int64_t)(100-amount)*av+(int64_t)amount*bv,100),0,4095,&st->clamps);
                put16(o+at+2*j,v);
            } else {
                int aa=(at==82 || at==379 || at==412)?20:at==346?284:456;
                int av=interp_q16(a+aa,a+at,node(b+aa,j));
                v=kv_round_div((int64_t)(100-amount)*av+(int64_t)amount*b[at+j]*65536,100*65536);
                v=clip(v,0,255,&st->clamps);if(v<prev){st->monotone_repairs++;v=prev;}
                o[at+j]=(uint8_t)v;prev=v;
            }
        }
        if(n==96)for(j=0;j<96;j+=4){
            if(a[at+j+2]==(a[at+j+1]^128) && a[at+j+3]==a[at+j] && b[at+j+2]==(b[at+j+1]^128) && b[at+j+3]==b[at+j]){
                o[at+j+2]=o[at+j+1]^128;o[at+j+3]=o[at+j];
            }
        }
    }
}

static int warp(int y,int lo,int hi,int s)
{
    int64_t n,d,t=y-lo,length=hi-lo;int j,rem,gain;
    if(!s || y<=lo || y>=hi)return y;
    j=abs_i(s)/64;rem=abs_i(s)%64;
    gain=j==256?exp_q12[j]:exp_q12[j]+kv_round_div((int64_t)(exp_q12[j+1]-exp_q12[j])*rem,64);
    n=s>0?gain:KV_Q;d=s>0?KV_Q:gain;
    return lo+kv_round_div(length*n*t,d*(length-t)+n*t);
}
static void tone_curve(uint8_t *p,const int32_t *d)
{
    int i,y,c=d[0],h=d[1],s=d[2],f=d[3],black=kv_round_div((int64_t)abs_i(f)*80,KV_Q);
    for(i=0;i<33;i++){
        y=p[i];if(c)y=y<=128?warp(y,0,128,-c):warp(y,128,255,c);
        if(h)y=warp(y,112,255,h);
        if(s)y=warp(y,0,144,s);
        if(f)y=kv_round_div((int64_t)black*255+(255-black)*y,255);
        p[i]=(uint8_t)y;
    }
}

static KV_STAGE_FN void saturation(uint8_t *b,int dose,KvStats *st,KvStage *stage)
{
    int32_t *w=stage->matrix.w;int i,cm=0,mm=0,wanted,cg,residual,mg;
    if(!dose)return;
    matrix_read(b,w);
    wanted=dose>0?KV_Q+3*dose:kv_round_div((int64_t)KV_Q*KV_Q,KV_Q+3*abs_i(dose));
    for(i=0;i<96;i++)cm=max_i(cm,b[115+i]&127);
    for(i=0;i<28;i++)if(i%14>=3 && i%14<9)mm=max_i(mm,abs_i(w[i]));
    cg=min_i(wanted,cm?127*KV_Q/cm:wanted);residual=kv_round_div((int64_t)wanted*KV_Q,cg);
    mg=min_i(residual,mm?1279*KV_Q/mm:residual);
    st->colour_cap+=cg<wanted;st->matrix_cap+=mg<residual;
    for(i=0;i<96;i++)b[115+i]=(uint8_t)((b[115+i]&128)|kv_round_div((int64_t)(b[115+i]&127)*cg,KV_Q));
    if(mg!=KV_Q){for(i=0;i<28;i++)if(i%14>=3 && i%14<9)w[i]=(w[i]>=0?1:-1)*kv_round_div((int64_t)abs_i(w[i])*mg,KV_Q);matrix_store(b,w);}
}

static KV_STAGE_FN int add_rowsum(uint8_t *b,int cb,int cr,KvStats *st,KvStage *stage)
{
    int32_t *w=stage->matrix.w,*dd=stage->matrix.dd,*delta=stage->matrix.delta;
    int half,row,i,j,amount,alpha=KV_Q,sum,ys;
    kv_zero(dd,28*sizeof(*dd));
    if(!cb && !cr)return 0;
    matrix_read(b,w);
    for(half=0;half<=14;half+=14){
        ys=w[half]+w[half+1]+w[half+2];if(ys<=0)return -2;
        j=0;for(i=1;i<3;i++)if(abs_i(w[half+i])>abs_i(w[half+j]))j=i;
        for(row=3;row<=6;row+=3){amount=row==3?cb:cr;sum=0;
            for(i=0;i<3;i++){delta[i]=kv_round_div((int64_t)amount*w[half+i],ys);sum+=delta[i];}
            delta[j]+=amount-sum;for(i=0;i<3;i++)dd[half+row+i]=delta[i];
        }
    }
    for(i=0;i<28;i++){
        if(dd[i]>0)alpha=min_i(alpha,(1279-w[i])*KV_Q/dd[i]);
        else if(dd[i]<0)alpha=min_i(alpha,(-1279-w[i])*KV_Q/dd[i]);
    }
    alpha=clip(alpha,0,KV_Q,NULL);st->rowsum_cap+=alpha<KV_Q;
    for(i=0;i<28;i++)w[i]+=kv_round_div((int64_t)dd[i]*alpha,KV_Q);
    matrix_store(b,w);return 0;
}

static KV_STAGE_FN void bw_filter(uint8_t *b,int dose,KvStage *stage)
{
    static const int green[3]={96,896,32};
    static const int positive[3][3]={{420,580,24},{700,300,24},{930,80,14}};
    int32_t *w=stage->matrix.w,*a=stage->matrix.a,*bb=stage->matrix.bb,*v=stage->matrix.v;
    int half,i,j,t,seg,sum;
    if(!dose)return;
    matrix_read(b,w);
    for(half=0;half<=14;half+=14){
        if(dose<0){kv_copy(a,w+half,3*sizeof(*a));kv_copy(bb,green,3*sizeof(*bb));t=-dose;}
        else {int p=dose*3;seg=min_i(2,p/KV_Q);t=p-seg*KV_Q;
            if(seg==0)kv_copy(a,w+half,3*sizeof(*a));else kv_copy(a,positive[seg-1],3*sizeof(*a));
            kv_copy(bb,positive[seg],3*sizeof(*bb));}
        sum=0;j=0;for(i=0;i<3;i++){v[i]=kv_round_div((int64_t)(KV_Q-t)*a[i]+(int64_t)t*bb[i],KV_Q);sum+=v[i];if(v[i]>v[j])j=i;}
        v[j]+=1024-sum;for(i=0;i<3;i++)w[half+i]=v[i];
    }
    matrix_store(b,w);
}

static void t1(uint8_t *b,int warmth,int tint,int split,KvStats *st)
{
    int at,j,sign,y,gain;
    if(!warmth && !tint && !split)return;
    if(!(b[1]&2)){kv_copy(b+379,b+82,33);kv_copy(b+412,b+82,33);}
    b[1]|=6;put16(b+445,0);
    for(at=379;at<=412;at+=33){sign=at==379?1:-1;
        for(j=0;j<33;j++){
            y=b[at+j];gain=KV_Q+kv_round_div((int64_t)3*abs_i(warmth),5);
            if(warmth*sign>0)y=kv_round_div((int64_t)y*gain,KV_Q);
            else if(warmth*sign<0)y=kv_round_div((int64_t)y*KV_Q,gain);
            gain=KV_Q+kv_round_div(abs_i(tint),2);
            if(tint>0)y=kv_round_div((int64_t)y*gain,KV_Q);
            else if(tint<0)y=kv_round_div((int64_t)y*KV_Q,gain);
            y=clip(y,0,255,&st->clamps);
            if(split)y=y<=128?warp(y,0,128,-sign*split):warp(y,128,255,sign*split);
            b[at+j]=(uint8_t)clip(y,0,255,&st->clamps);
        }
    }
}

static KV_STAGE_FN int apply_stages(const uint8_t *stock,KvWork *work)
{
    uint8_t *b=work->result;
    const KvRequest *r=&work->request;
    KvStats *st=&work->stats;
    KvStage *stage=&work->stage;
    int status,warm,tint;
    blend(b,stock,work->base,r->amount,st,stage);
    if(!(b[1]&1))kv_copy(b+216,stock+216,56);
    if(r->dose[0] || r->dose[1] || r->dose[2] || r->dose[3]){
        tone_curve(b+82,r->dose);tone_curve(b+518,r->dose);
        if(b[1]&16)tone_curve(b+346,r->dose);
        if(b[1]&2){tone_curve(b+379,r->dose);tone_curve(b+412,r->dose);}
    }
    saturation(b,r->dose[4],st,stage);bw_filter(b,r->dose[8],stage);
    if(r->wb_method==0){
        status=add_rowsum(b,kv_round_div((int64_t)-140*r->dose[5]+100*r->dose[6],KV_Q),kv_round_div((int64_t)180*r->dose[5]+110*r->dose[6],KV_Q),st,stage);
        if(status)return status;
        warm=tint=0;
    }else {warm=r->dose[5];tint=r->dose[6];}
    if(r->dose[9]){
        if(r->tone_method==0){status=add_rowsum(b,kv_round_div((int64_t)-128*r->dose[9],KV_Q),kv_round_div((int64_t)128*r->dose[9],KV_Q),st,stage);if(status)return status;}
        else {int32_t *w=stage->matrix.w;int half;matrix_read(b,w);for(half=0;half<=14;half+=14){w[half+10]=clip(w[half+10]+kv_round_div((int64_t)-8*r->dose[9],KV_Q),120,136,&st->clamps);w[half+11]=clip(w[half+11]+kv_round_div((int64_t)8*r->dose[9],KV_Q),120,136,&st->clamps);}matrix_store(b,w);}
    }
    t1(b,warm,tint,r->dose[7],st);limit_slopes(b,st);checksum(b);
    return 0;
}

int kv_apply_work(const uint8_t stock[KV_BYTES],const uint8_t base[KV_BYTES],const KvRequest *r,
                  uint8_t out[KV_BYTES],KvStats *stats,KvWork *work)
{
    int i,active=0,status;
    if(!stock || !base || !r || !out || !stats || !work || r->amount<0 || r->amount>150 ||
       r->dose[KV_FADE]<0 || r->wb_method<0 || r->wb_method>1 || r->tone_method<0 || r->tone_method>1)return -1;
    for(i=0;i<10;i++){if(r->dose[i]<-max_dose[i] || r->dose[i]>max_dose[i])return -1;active|=r->dose[i]!=0;}
    kv_move(&work->request,r,sizeof(*r));
    kv_move(work->base,base,KV_BYTES);
    kv_zero(&work->stats,sizeof(work->stats));
    if((work->request.amount==100 || work->request.amount==0) && !active){
        kv_move(out,work->request.amount==100?work->base:stock,KV_BYTES);
    }else{
        status=apply_stages(stock,work);if(status)return status;
        kv_move(out,work->result,KV_BYTES);
    }
    kv_move(stats,&work->stats,sizeof(*stats));
    return 0;
}
