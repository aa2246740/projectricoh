#ifndef PROJECTRICOH_HOST_FILE_STORE_H
#define PROJECTRICOH_HOST_FILE_STORE_H

#include "../recipe_storage.h"

typedef struct {
    const char *directory;
} HostFileStore;

RecipeStorage host_file_storage(HostFileStore *store);

#endif
