/* Host-only call into the original Stage2l table_valid implementation. */
#include <stdio.h>
#include <string.h>
#include "deep_isp.c"

int main(int argc, char **argv)
{
    unsigned char bytes[RFW_TABLE_BYTES + 1];
    FILE *stream;
    size_t length;
    uint32_t crc;
    int expected;
    if (argc != 3) return 2;
    expected = strcmp(argv[2], "accept") == 0;
    stream = fopen(argv[1], "rb");
    if (stream == NULL) return 3;
    length = fread(bytes, 1, sizeof(bytes), stream);
    if (ferror(stream)) { fclose(stream); return 4; }
    fclose(stream);
    crc = table_valid(bytes, length);
    printf("{\"accepted\":%s,\"bytes\":%zu,\"file_crc\":\"%08x\"}\n",
           crc != 0 ? "true" : "false", length, (unsigned)crc);
    return ((crc != 0) == expected) ? 0 : 1;
}
