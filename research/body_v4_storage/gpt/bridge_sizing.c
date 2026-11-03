/* Research sizing specimen. Not a firmware patch or an installable bridge.
 * Undefined port functions represent obligations, not implemented guarantees.
 * No Ricoh instruction bytes, executable addresses or device access here.
 */
#include <stdint.h>
#include <stddef.h>

enum { IDLE, QUEUED, RUNNING, DONE, FAULT, RETURNING };
enum { OK, BUSY, STALE, CANCELLED, IO_UNKNOWN, HANDLE_UNCERTAIN };
typedef struct { uint32_t boot, session, media, module; } Identity;
typedef struct {
    uint32_t id;
    Identity identity;
    uint32_t bank, selected_bank, length, data, crc, deadline, cookie;
} Job;
typedef struct {
    uint32_t id, cookie, status, stage, bytes, high_count, free_slots, media;
} Completion;
typedef struct {
    uint32_t phase, next_id, cancelled, disabled;
    Identity current;
    uint32_t accepted_capture, accepted_aux, active_producer, queued_native;
    Job job;
    Completion completion;
} Bridge;
Bridge storage_bridge;

/* These ports are deliberately unresolved in the research object. */
extern uint32_t port_irq_save(void);
extern void port_irq_restore(uint32_t);
extern int port_validate_and_pin(const Job *);
extern void port_unpin(const Job *);
extern int port_enqueue(uint32_t, uint32_t);
extern int port_exclusive_and_drained(void);
extern int port_open_existing(uint32_t);
extern int port_write_direct(int, const void *, uint32_t);
extern int port_read(int, void *, uint32_t);
extern int port_close(int);
extern uint32_t port_high_count(void);
extern uint32_t port_free_slots(void);
extern int port_same_media(void);
extern uint32_t port_geometry(int);

static int same_identity(const Identity *a, const Identity *b)
{
    return a->boot == b->boot && a->session == b->session &&
        a->media == b->media && a->module == b->module;
}

static int healthy(void)
{
    return port_high_count() == 0 && port_free_slots() == 2;
}

static int valid_now(void)
{
    return !storage_bridge.cancelled && !storage_bridge.disabled &&
        same_identity(&storage_bridge.job.identity, &storage_bridge.current) &&
        port_same_media();
}

int sizing_submit(const Job *job)
{
    uint32_t irq = port_irq_save();
    if (storage_bridge.phase != IDLE || storage_bridge.disabled ||
        !same_identity(&job->identity, &storage_bridge.current)) {
        port_irq_restore(irq);
        return BUSY;
    }
    if (job->id == 0 || job->id <= storage_bridge.next_id ||
        job->bank > 1 || job->selected_bank > 1 || job->bank == job->selected_bank ||
        (job->length != 8192 && job->length != 16384 &&
         job->length != 32768 && job->length != 65536)) {
        port_irq_restore(irq);
        return STALE;
    }
    storage_bridge.next_id = job->id;
    storage_bridge.job = *job;
    storage_bridge.cancelled = 0;
    storage_bridge.phase = QUEUED;
    port_irq_restore(irq);
    if (!port_validate_and_pin(&storage_bridge.job)) {
        storage_bridge.phase = IDLE;
        return STALE;
    }
    if (port_enqueue(job->id, job->cookie) != 0) {
        port_unpin(&storage_bridge.job);
        storage_bridge.phase = IDLE;
        return BUSY;
    }
    return OK;
}

void sizing_revoke(uint32_t media, uint32_t module)
{
    uint32_t irq = port_irq_save();
    storage_bridge.cancelled = 1;
    storage_bridge.current.media = media;
    storage_bridge.current.module = module;
    port_irq_restore(irq);
}

/* A fixed operation owns all native I/O. No DAT callback is accepted. */
int sizing_handle(uint32_t id, uint32_t cookie)
{
    Job *job = &storage_bridge.job;
    uint32_t q = 0, at = 0, status = BUSY;
    int fd = -1, closed = 0, rc;
    if (storage_bridge.phase != QUEUED || job->id != id || job->cookie != cookie)
        return STALE;
    if (!valid_now()) { status = STALE; goto done; }
    if (storage_bridge.accepted_capture || storage_bridge.accepted_aux ||
        storage_bridge.active_producer || storage_bridge.queued_native ||
        !port_exclusive_and_drained() || !healthy())
        goto done;
    storage_bridge.phase = RUNNING;
    fd = port_open_existing(job->bank);
    if (fd < 0) { status = IO_UNKNOWN; goto done; }
    q = port_geometry(fd);
    if (!q || q > 65536 || (q & (q - 1)) || q < 512 || job->length % q) {
        status = IO_UNKNOWN;
        goto cleanup;
    }
    while (at < job->length) {
        if (!valid_now()) { status = CANCELLED; goto cleanup; }
        rc = port_write_direct(fd, (const void *)(uintptr_t)(job->data + at), q);
        if (rc != (int)q) { status = IO_UNKNOWN; goto cleanup; }
        at += q;
    }
    status = OK;
cleanup:
    if (!port_same_media()) { status = HANDLE_UNCERTAIN; goto done; }
    closed = 1;
    rc = port_close(fd);
    if (rc || !healthy()) status = HANDLE_UNCERTAIN;
    fd = -1;
done:
    if (fd >= 0 && !closed) status = HANDLE_UNCERTAIN;
    if ((status == OK || status == IO_UNKNOWN) && !healthy()) status = HANDLE_UNCERTAIN;
    storage_bridge.completion.id = id;
    storage_bridge.completion.cookie = cookie;
    storage_bridge.completion.status = status;
    storage_bridge.completion.bytes = at;
    storage_bridge.completion.high_count = port_high_count();
    storage_bridge.completion.free_slots = port_free_slots();
    storage_bridge.completion.media = storage_bridge.current.media;
    /* Publication is completed by a permanent resident trampoline after return.
     * Readback, port implementations, admission hooks and recovery are excluded.
     */
    storage_bridge.phase = status == HANDLE_UNCERTAIN ? FAULT : RETURNING;
    return (int)status;
}

uint32_t sizing_job_bytes(void) { return sizeof(Job); }
uint32_t sizing_bridge_bytes(void) { return sizeof(Bridge); }
