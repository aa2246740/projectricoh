#include <stdint.h>
#include <stdio.h>

uint32_t gxr2_crc_zeroed(const uint8_t *, size_t, size_t, size_t);

int main(void)
{
    uint8_t block[17385];
    size_t count = fread(block, 1, sizeof(block), stdin);
    if (count != 17384 || ferror(stdin)) return 1;
    printf("%08x\n", (unsigned)gxr2_crc_zeroed(block, count, 16, 4));
    return 0;
}
