#define main original_host_suite_main
#include "test_host.c"
#undef main

int main(int argc, char **argv)
{
    CHECK(argc == 4);
    binding = rfw_closed_table;
    test_library = argv[1];
    load_image(argv[2], table_equal, sizeof(table_equal));
    load_image(argv[2], table_new, sizeof(table_new));
    history_case(argv[3]);
    return 0;
}
