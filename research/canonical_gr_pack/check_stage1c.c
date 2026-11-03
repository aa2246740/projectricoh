#include "recipe_v1.h"
#include <stdio.h>
#include <stdlib.h>

/* Read the delivered DAT with the existing Stage 1c C consumer. */
int main(int argc, char **argv)
{
    uint8_t bytes[RV1_FILE_BYTES + 1];
    Rv1Bank bank;
    FILE *file;
    size_t length;
    if (argc != 2 || !(file = fopen(argv[1], "rb"))) return 2;
    length = fread(bytes, 1, sizeof(bytes), file);
    if (fclose(file) || rv1_decode(bytes, length, &bank, NULL) != RV1_OK) return 3;
    printf("[");
    for (size_t i = 0; i < 16; ++i) {
        Rv1WritePlan plan;
        if (!bank.slots[i].occupied || rv1_plan(&bank.slots[i].recipe, &plan) != RV1_OK) return 4;
        printf("%s[", i ? "," : "");
        for (size_t j = 0; j < plan.count; ++j)
            printf("%s[%u,%u]", j ? "," : "", plan.writes[j].offset, plan.writes[j].value);
        printf("]");
    }
    puts("]");
    return 0;
}
