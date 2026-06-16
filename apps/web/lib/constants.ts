// Safety timeout for async agent jobs (digest regen, Eve insight). Couples to
// worker latency: the SSE completion event normally clears UI state well before
// this fires; it only guards against a dropped event leaving a spinner stuck.
export const ASYNC_JOB_TIMEOUT_MS = 45_000;
