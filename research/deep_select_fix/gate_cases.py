#!/usr/bin/env python3
"""Host model of the recipe-page gate. Does not build or touch firmware."""

IMAGE = 8
ISO = 6
TYPE_IMAGE = 5
TYPE_ISO = 3
TYPE_CASE7 = 6
PART = 2
TAG = 33
STATE = 0x2022F71C
DEEP_SLOTS = {1, 2, 3, 5}


def ui_active(activity, part, count, list_type, tag, state, entries_null=False):
    """Same predicate as payload rfw_ui_active at 0x20052CE0."""
    if activity != IMAGE or part != PART or count == 0 or count > 2 or list_type != TYPE_IMAGE:
        return False
    if entries_null:
        return False
    return tag == TAG and state == STATE


def commit(active, select_status):
    """Current payload: any active page consumes the key, even with no preview."""
    if not active:
        return "stock"
    return "payload" if select_status == "preview" else "swallowed"


def acquire(slot, load_ok, preflight, uncertain=False):
    """Current deep acquire. Preflight miss aborts S writes and preview."""
    if not load_ok:
        return "empty"
    if slot in DEEP_SLOTS:
        if uncertain or not preflight:
            return "conflict"
    return "preview"


def acquire_fixed(slot, load_ok, preflight, uncertain=False):
    """Design: a preflight miss before any W still publishes S and requests preview."""
    if not load_ok:
        return "empty"
    if slot in DEEP_SLOTS and uncertain:
        return "conflict"
    return "preview"


def check(cond, text):
    if not cond:
        raise SystemExit("FAIL " + text)


def main():
    recipe = dict(activity=IMAGE, part=PART, count=1, list_type=TYPE_IMAGE,
                  tag=TAG, state=STATE)
    check(ui_active(**recipe), "recipe page")
    check(ui_active(**{**recipe, "count": 2}), "two stack entries")
    check(not ui_active(**{**recipe, "activity": ISO, "list_type": TYPE_ISO}), "ISO")
    check(not ui_active(**{**recipe, "activity": 7, "list_type": TYPE_CASE7}), "case 7")
    for activity, list_type in ((9, 0), (11, 0), (12, 0), (1, 0), (3, 0)):
        check(not ui_active(**{**recipe, "activity": activity, "list_type": list_type}),
              f"activity {activity}")
    check(not ui_active(**{**recipe, "activity": ISO, "list_type": TYPE_IMAGE}),
          "stale type 5 under ISO")
    check(not ui_active(**{**recipe, "list_type": TYPE_ISO}), "image activity wrong type")
    check(not ui_active(**{**recipe, "part": 1}), "wrong part")
    check(not ui_active(**{**recipe, "tag": 9}), "wrong tag")
    check(not ui_active(**{**recipe, "state": 0x2022DB60}), "wrong state")
    check(not ui_active(**{**recipe, "entries_null": True}), "null entries")
    check(not ui_active(**{**recipe, "count": 0}), "count 0")
    check(not ui_active(**{**recipe, "count": 3}), "count 3")

    check(commit(True, "preview") == "payload", "active select runs")
    check(commit(False, "preview") == "stock", "ISO passthrough")
    check(commit(True, "empty") == "swallowed", "current bug: failed select eats the key")

    for slot in range(1, 17):
        check(acquire_fixed(slot, True, False) == "preview", f"fixed slot {slot}")
        if slot in DEEP_SLOTS:
            check(acquire(slot, True, False) == "conflict", f"current deep slot {slot}")
        else:
            check(acquire(slot, True, False) == "preview", f"current plain slot {slot}")
    check(all(len(n) <= 8 for n in NAMES), "names fit")
    check(len(NAMES) == 16 and len(set(NAMES)) == 16, "16 distinct names")
    print("PASS", len(NAMES), "names;", "gate recipe true; ISO/case7/other activities false")


NAMES = [
    "01 Posi", "02 Nega", "03 HC BW", "04 Std", "05 Blch", "06 SftBW",
    "07 Sepia", "08 ClBW", "09 Cross", "10 Vivid", "11 Natur", "12 B&W",
    "13 XMag", "14 XYel", "15 RedTE", "16 GrnTE",
]


if __name__ == "__main__":
    main()
