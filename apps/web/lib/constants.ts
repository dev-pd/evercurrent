// Safety timeout for async agent jobs. Couples to worker latency: the SSE
// completion event normally clears UI state well before this fires; it only
// guards against a dropped event leaving a spinner stuck.
// Digest regen is a single ~20s Sonnet call.
export const ASYNC_JOB_TIMEOUT_MS = 45_000;
// Eve is a multi-turn agent loop (up to 8 Sonnet calls), routinely 50-90s.
export const EVE_JOB_TIMEOUT_MS = 120_000;
