#include "internal.h"

static const uint16_t offsets[RV1_COLOR_BYTES] = {
    0x36f,0x370,0x371,0x8ac,0x8ad,0x8ae,0x8af,0x8b0,0x8b1,0x8b2,0x8b3,0x8b4,0x8b5
};
static const uint16_t bw_offsets[2] = {0x645, 0x646};
static const uint16_t te_offsets[4] = {0x641, 0x642, 0x644, 0x643};

Rv1Status rv1_plan(const Rv1Recipe *recipe, Rv1WritePlan *plan)
{
    size_t i, count;
    const uint16_t *fields;
    Rv1Status status = rv1_validate_recipe(recipe);
    if (status != RV1_OK) return status;
    if (plan == NULL) return RV1_ARGUMENT;
    if (recipe->base_mode == RV1_BASE_COLOR) { fields = offsets; count = 13; }
    else if (recipe->base_mode == RV1_BASE_BW) { fields = bw_offsets; count = 2; }
    else { fields = te_offsets; count = 4; }
    for (i = 0; i < count; ++i) {
        plan->writes[i].offset = fields[i];
        plan->writes[i].value = recipe->raw[i];
    }
    plan->writes[count].offset = RV1_WB0_OFFSET;
    plan->writes[count++].value = (uint8_t)((int)recipe->wb[0] + 9);
    plan->writes[count].offset = RV1_WB1_OFFSET;
    plan->writes[count++].value = (uint8_t)((int)recipe->wb[1] + 9);
    plan->writes[count].offset = RV1_SELECTOR_OFFSET;
    plan->writes[count++].value = recipe->base_mode;
    plan->count = (uint8_t)count;
    return RV1_OK;
}

Rv1Status rv1_apply(const Rv1SettingsPort *port, const Rv1Recipe *recipe)
{
    volatile uint8_t *s = NULL;
    size_t length = 0, i;
    Rv1WritePlan plan;
    Rv1Status status = rv1_plan(recipe, &plan);
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
    for (i = 0; i < plan.count; ++i)
        s[plan.writes[i].offset] = plan.writes[i].value;
    status = port->request_preview(port->context);
    port->release(port->context, 1);
    return status;
}
