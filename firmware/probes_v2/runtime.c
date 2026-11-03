#include <stddef.h>
void *memcpy(void *destination,const void *source,size_t bytes)
{
    unsigned char *d=destination; const unsigned char *s=source;
    while (bytes--) *d++=*s++;
    return destination;
}
