#define main inherited_main
#include REVIEW_HOST_SOURCE
#undef main

static void emit_live(unsigned slot,int tweak)
{
    unsigned row,j;uint32_t map=be32(new_raw+be32(new_raw+156)+64*unit+12);
    printf("VECTOR %u %d ",slot,tweak);
    for(row=0;row<9;row++){
        const uint8_t *d=new_raw+map+32+12*row,*p=RV_PTR(be32(d));
        for(j=0;j<be16(d+4);j++)printf("%02x",p[j]);
    }
    printf(" %u ",t_control);
    for(j=0;j<4096;j++)printf("%02x",RV_BYTE(0x20500000+j));puts("");
}
int main(int argc,char **argv)
{
    char *args[8];unsigned i,slot,level;CHECK(argc==8);
    for(i=0;i<8;i++)args[i]=argv[i];args[1]="basic";CHECK(inherited_main(argc,args)==0);
    for(slot=1;slot<=8;slot++){
        clean();ready(1);menu();apply_ok(slot);matches_recipe(new_raw,slot,new_golden);emit_live(slot,0);
        for(level=1;level<=2;level++){
            menu();open_fn2();select_slot(level==1?8:3);
            explicit_apply=flush_allowed=1;close_key(1);explicit_apply=flush_allowed=0;
            current(level==1?2:-3);emit_live(slot,level==1?2:-3);
        }
    }
    printf("OK differential unit=%u assertions=%u\n",unit,assertions);return 0;
}
