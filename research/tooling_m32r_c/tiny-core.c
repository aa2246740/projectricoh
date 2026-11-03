typedef unsigned char u8;
typedef unsigned int u32;

_Static_assert(sizeof(u8) == 1, "u8 width");
_Static_assert(sizeof(u32) == 4, "u32 width");
_Static_assert(sizeof(void *) == 4, "pointer width");

typedef struct {
    u8 name_length;
    u8 name[32];
    u8 color[13];
} TinyRecipe;

_Static_assert(sizeof(TinyRecipe) == 46, "recipe size");

u32 tiny_recipe_checksum(const TinyRecipe *recipe)
{
    const u8 *bytes = (const u8 *) recipe;
    u32 value = 2166136261u;
    u32 index;

    for (index = 0; index < (u32) sizeof(*recipe); ++index) {
        value ^= bytes[index];
        value *= 16777619u;
    }
    return value;
}

int tiny_recipe_copy(TinyRecipe *destination, const TinyRecipe *source)
{
    u32 index;

    if (destination == (TinyRecipe *) 0 || source == (const TinyRecipe *) 0) {
        return -1;
    }
    if (source->name_length > 32u) {
        return -2;
    }
    for (index = 0; index < (u32) sizeof(*destination); ++index) {
        ((u8 *) destination)[index] = ((const u8 *) source)[index];
    }
    return 0;
}
