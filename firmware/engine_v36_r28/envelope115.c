#include "resident.h"
#include <stdio.h>
#include <stdlib.h>
int main(int argc,char **argv)
{
    uint8_t raw[RV_MAX_FILE+4];size_t n;FILE *f;GxrceView v;GxrceStatus result;
    if(argc!=2||(f=fopen(argv[1],"rb"))==NULL)return 2;
    n=fread(raw,1,sizeof(raw),f);if(ferror(f)||fgetc(f)!=EOF||fclose(f))return 2;
    result=rv_validate(raw,n,&rv_trust,&v);printf("%u\n",result);return 0;
}
