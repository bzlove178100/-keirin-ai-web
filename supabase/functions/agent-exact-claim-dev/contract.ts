export const EXACT_CLAIM_SERVICE = 'agent-exact-claim-dev';
export const EXACT_CLAIM_VERSION = 'v1-owner-trusted-run-exact-claim';
export const EXACT_CLAIM_MODE = 'queue_claim_task';

export const EXACT_CLAIM_SAFETY = Object.freeze({
  runtime_task_execution_enabled: false,
  production_prediction_enabled: false,
  keirin_prediction_db_write_enabled: false,
  external_keirin_auto_fetch_enabled: false,
  provider_generation_enabled: false,
  report_delivery_enabled: false,
  exact_queue_claim_enabled: true,
});

const TRUSTED_RUN_ID_RE = /^keirin-readonly-status-check\.[0-9a-f]{16,32}$/;
const WORKER_ID_RE = /^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$/;
const ALLOWED_KEYS = new Set(['mode', 'task_id', 'worker_id', 'lease_seconds']);

function asObject(value: unknown): Record<string, unknown> | null {
  return value && typeof value === 'object' && !Array.isArray(value)
    ? value as Record<string, unknown>
    : null;
}

export function validateExactClaimRequest(input: unknown) {
  const body = asObject(input);
  if (!body) return { ok: false, error: 'request must be an object' } as const;
  const unknown = Object.keys(body).filter((key) => !ALLOWED_KEYS.has(key));
  if (unknown.length) return { ok: false, error: 'unexpected request fields' } as const;
  if (body.mode !== EXACT_CLAIM_MODE) return { ok: false, error: 'exact claim mode required' } as const;

  const taskId = typeof body.task_id === 'string' && TRUSTED_RUN_ID_RE.test(body.task_id)
    ? body.task_id
    : null;
  if (!taskId) return { ok: false, error: 'trusted run-instance task_id required' } as const;

  const workerId = typeof body.worker_id === 'string' && WORKER_ID_RE.test(body.worker_id)
    ? body.worker_id
    : null;
  if (!workerId) return { ok: false, error: 'valid worker_id required' } as const;

  const leaseSeconds = body.lease_seconds;
  if (!Number.isSafeInteger(leaseSeconds) || (leaseSeconds as number) < 15 || (leaseSeconds as number) > 3600) {
    return { ok: false, error: 'lease_seconds must be an integer from 15 to 3600' } as const;
  }

  return {
    ok: true,
    task_id: taskId,
    worker_id: workerId,
    lease_seconds: leaseSeconds as number,
  } as const;
}
