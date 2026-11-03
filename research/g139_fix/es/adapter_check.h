/* g139 copy of research/emptystack_v38/adapter_check.h: adds n.spare.io.preselect (uv_move clears it). */
#include <assert.h>
#include <limits.h>
#include <stdlib.h>
#include "ui_v2_data.h"
enum { UV_L1,UV_CARD,UV_ITEMS,UV_VALUE,UV_GROUP,UV_ENTRIES,UV_ERR };
static struct {
    struct {unsigned physical,cur,screen,slot,count,last_cur,armed,applied_user;UvLevels levels,saved[32];KvUiNav nav;}ui;
    UvLevels values[8];
    struct {struct {unsigned char preselect;} io;} spare;   /* g139: P1-03 offer, cleared by a move */
} n;
#define uv_nav_load() abort()
#define uv_nav_accept(a) abort()
#define uv_preview(a,b,c) ((void)(a),(void)(b),(void)(c),abort(),ENG_REJECTED)
#define eng_knobs_view() (abort(),(const KvDataView *)0)
#define eng_validated_view() (abort(),(const Gxr2View *)0)
#define pn_equal(a,b,c) 1
#define uv_group_entry(a) (abort(),0u)

