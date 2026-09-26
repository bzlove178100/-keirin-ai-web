import {
  EXACT_CLAIM_MODE,
  EXACT_CLAIM_SAFETY,
  EXACT_CLAIM_SERVICE,
  EXACT_CLAIM_VERSION,
  validateExactClaimRequest,
} from '../supabase/functions/agent-exact-claim-dev/contract.ts';

function assert(condition: unknown, message: string): asserts condition {
  if (!condition) throw new Error(message);
}

Deno.test('exact-claim service is queue-only and does not enable execution', () => {
  assert(EXACT_CLAIM_SERVICE === 'agent-exact-claim-dev', 'service changed unexpectedly');
  assert(EXACT_CLAIM_VERSION === 'v1-owner-trusted-run-exact-claim', 'version changed unexpectedly');
  assert(EXACT_CLAIM_MODE === 'queue_claim_task', 'only exact claim mode is allowed');
  assert(EXACT_CLAIM_SAFETY.runtime_task_execution_enabled === false, 'task execution must remain disabled');
  assert(EXACT_CLAIM_SAFETY.production_prediction_enabled === false, 'production prediction must remain off');
  assert(EXACT_CLAIM_SAFETY.keirin_prediction_db_write_enabled === false, 'prediction DB writes must remain off');
  assert(EXACT_CLAIM_SAFETY.external_keirin_auto_fetch_enabled === false, 'external fetch must remain off');
  assert(EXACT_CLAIM_SAFETY.provider_generation_enabled === false, 'provider generation must remain off');
  assert(EXACT_CLAIM_SAFETY.report_delivery_enabled === false, 'report delivery must remain off');
  assert(EXACT_CLAIM_SAFETY.exact_queue_claim_enabled === true, 'exact claim should be explicit');
});

Deno.test('exact claim accepts only trusted run-instance ids and bounded worker leases', () => {
  const valid = validateExactClaimRequest({
    mode: 'queue_claim_task',
    task_id: 'keirin-readonly-status-check.0123456789abcdef',
    worker_id: 'worker-a:host.1',
    lease_seconds: 180,
  });
  assert(valid.ok === true, 'valid exact claim rejected');

  assert(validateExactClaimRequest({
    mode: 'queue_claim_task',
    task_id: 'keirin-readonly-status-check',
    worker_id: 'worker-a',
    lease_seconds: 180,
  }).ok === false, 'completed template id must not be claimable');

  assert(validateExactClaimRequest({
    mode: 'queue_claim_task',
    task_id: 'other-task.0123456789abcdef',
    worker_id: 'worker-a',
    lease_seconds: 180,
  }).ok === false, 'untrusted task prefix must fail');

  assert(validateExactClaimRequest({
    mode: 'queue_claim_task',
    task_id: 'keirin-readonly-status-check.0123456789abcdef',
    worker_id: '../bad',
    lease_seconds: 180,
  }).ok === false, 'path-like worker id must fail');

  assert(validateExactClaimRequest({
    mode: 'queue_claim_task',
    task_id: 'keirin-readonly-status-check.0123456789abcdef',
    worker_id: 'worker-a',
    lease_seconds: 5,
  }).ok === false, 'short lease must fail');
});

Deno.test('exact claim rejects extra fields and every non-exact mode', () => {
  const common = {
    task_id: 'keirin-readonly-status-check.0123456789abcdef',
    worker_id: 'worker-a',
    lease_seconds: 120,
  };
  assert(validateExactClaimRequest({ mode: 'queue_claim', ...common }).ok === false, 'FIFO mode must fail');
  assert(validateExactClaimRequest({ mode: 'execute', ...common }).ok === false, 'execute mode must fail');
  assert(validateExactClaimRequest({ mode: 'queue_claim_task', ...common, unexpected: true }).ok === false,
    'extra fields must fail closed');
});
