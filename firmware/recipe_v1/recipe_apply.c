#include "internal.h"

static const uint16_t offsets[RV1_COLOR_BYTES] = {
    0x36f,0x370,0x371,0x8ac,0x8ad,0x8ae,0x8af,0x8b0,0x8b1,0x8b2,0x8b3,0x8b4,0x8b5
};

Rv1Status rv1_apply(const Rv1SettingsPort *port, const Rv1Recipe *recipe)
{
    volatile uint8_t *s = NULL;
    size_t length = 0, i;
    Rv1Status status = rv1_validate_recipe(recipe);
    if (status != RV1_OK) return status;
    if (port == NULL || port->acquire == NULL ||
        port->request_preview == NULL || port->release == NULL)
        return RV1_ARGUMENT;
    status = port->acquire(port->context, &s, &length);
    if (status != RV1_OK) return status;
    if (s == NULL || length < RV1_SETTINGS_MIN_BYTES) {
        port->release(port->context, 0);
        return RV1_LENGTH;
    }
    for (i = 0; i < RV1_COLOR_BYTES; ++i) s[offsets[i]] = recipe->raw[i];
    s[RV1_WB0_OFFSET] = (uint8_t)((int)recipe->wb[0] + 9);
    s[RV1_WB1_OFFSET] = (uint8_t)((int)recipe->wb[1] + 9);
    /* Publish Setting1 only after its color and WB fields are complete. */
    s[RV1_SELECTOR_OFFSET] = RV1_SELECTOR_SETTING1;
    status = port->request_preview(port->context);
    port->release(port->context, 1);
    return status;
}
