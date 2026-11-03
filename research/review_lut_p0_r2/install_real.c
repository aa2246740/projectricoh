#define main original_main
#include "../../firmware/lut_p0_timing/host_checks.c"
#undef main
int main(int argc,char **argv)
{
    unsigned j,i;Gxr2View v;RvSession *s;CHECK(argc==5);
    probe_bytes=read_file(argv[1],probe_raw);
    memset(&product_trust,0,sizeof(product_trust));
    memcpy(product_trust.body_sha256,rv_trust.body,32);
    memcpy(product_trust.resident_build_id,rv_trust.build,32);
    memcpy(product_trust.resident_abi_id,rv_trust.abi,16);
    for(i=0;i<3;++i){static const char names[3][8]={"jlaunch","qlaunch","l08firm"};
        memcpy(product_trust.modules[i].unit.name,names[i],8);
        product_trust.modules[i].unit.main_version=0x151;
        product_trust.modules[i].stock_crc32=rv_pins[i];}
    for(j=2;j<5;++j){
        full_bytes=read_file(argv[j],full_raw);installed_generation=rv_be32(full_raw+28);
        CHECK(installed_generation==111+j);
        CHECK(gxr2_gate_validate(full_raw,full_bytes,&product_trust,&product_trust.modules[0].unit,0,&v)==GXR2_OK);
        CHECK(gxr2_gate_validate(probe_raw,probe_bytes,&product_trust,&product_trust.modules[0].unit,0,&v)==GXR2_VERSION);
        install_rejection(installed_generation,1);install_rejection(installed_generation,0);
        reset();enter();CHECK(rv_session(&root)->generation==1);unchanged();
        reset();files[2].exists=0;rv_reset(&root);CHECK(rv_load(&root,&rv_trust)==RV_OK);
        s=rv_session(&root);CHECK(s&&s->selected_source==RV_SOURCE_A&&s->generation==installed_generation);
        unchanged();CHECK(!write_calls);
        reset();files[2].exists=files[0].exists=0;rv_reset(&root);CHECK(rv_load(&root,&rv_trust)==RV_OK);
        s=rv_session(&root);CHECK(s&&s->selected_source==RV_SOURCE_B&&s->generation==installed_generation);
        unchanged();CHECK(!write_calls);
        printf("PASS real product gen=%u bytes=%u product_gate=VERSION ps_install=VERIFY/envelope_CONFLICT loader=card1/fallbackA/B unchanged=1\n",installed_generation,full_bytes);
    }
    return 0;
}
