import {
  ACTIVITY_MODES,
  AGENT_RUNTIME_VERSION,
  CHECKPOINT_MODES,
  QUEUE_MODES,
  RUNTIME_CAPABILITIES,
  SAFETY_STATE,
  capabilityDiagnostics,
  findForbiddenSecretPath,
  preflightTask,
  validateActivityAppend,
  validateActivityList,
  validateCheckpointCreate,
  validateCheckpointSave,
  validateQueueClaim,
  validateQueueReconcileExpired,
  validateQueueSave,
  validateTaskId,
  validateWorkerId,
} from '../supabase/functions/agent-runtime-dev/contract.ts';

function assert(condition: unknown, message: string): asserts condition {
  if (!condition) throw new Error(message);
}

Deno.test('hosted agent runtime v6 enables durable queue coordination but not task execution', () => {
  assert(AGENT_RUNTIME_VERSION === 'v6-owner-queue-lease-fencing', 'runtime version changed unexpectedly');
  assert(SAFETY_STATE.production_prediction_enabled === false, 'production prediction must remain off');
  assert(SAFETY_STATE.db_write_enabled === false, 'keirin database writing must remain off');
  assert(SAFETY_STATE.external_automatic_fetch_enabled === false, 'external automatic fetching must remain off');
  assert(SAFETY_STATE.runtime_task_execution_enabled === false, 'runtime task execution must remain off in v6');
  assert(SAFETY_STATE.persistence_enabled === true, 'agent checkpoint persistence must remain enabled');
  assert(SAFETY_STATE.checkpoint_persistence_scope === 'agent_only', 'persistence scope must remain agent-only');
  assert(SAFETY_STATE.activity_persistence_enabled === true, 'append-only activity persistence must remain enabled');
  assert(SAFETY_STATE.queue_coordination_enabled === true, 'queue coordination should be explicitly enabled');
});

Deno.test('persistence and queue modes are explicit and never include execution', () => {
  for (const mode of ['checkpoint_create', 'checkpoint_get', 'checkpoint_list', 'checkpoint_save']) {
    assert(CHECKPOINT_MODES.includes(mode as never), `${mode} missing`);
  }
  for (const mode of ['event_append', 'event_list']) {
    assert(ACTIVITY_MODES.includes(mode as never), `${mode} missing`);
  }
  for (const mode of ['queue_claim', 'queue_save', 'queue_reconcile_expired']) {
    assert(QUEUE_MODES.includes(mode as never), `${mode} missing`);
  }
  assert(!QUEUE_MODES.includes('execute' as never), 'queue modes must not enable execution');
});

Deno.test('all external provider capabilities remain explicitly unbound', () => {
  assert(RUNTIME_CAPABILITIES.length >= 13, 'expected shared runtime capability declarations');
  assert(RUNTIME_CAPABILITIES.every((cap) => cap.bound === false), 'no provider capability may be silently bound');
  const delivery = RUNTIME_CAPABILITIES.find((cap) => cap.action === 'report.deliver');
  assert(delivery?.access === 'write', 'report delivery must be classified as a write');
  assert(delivery?.supports_dry_run === false, 'report delivery must not pretend to support dry-run');
});

Deno.test('broad generation/evaluation capabilities remain declared but provider-unbound', () => {
  const required = new Map([
    ['research.read_public_sources', 'read'],
    ['text.generate', 'execute'],
    ['image.generate', 'execute'],
    ['video.generate', 'execute'],
    ['code.generate', 'execute'],
    ['learning.evaluate', 'execute'],
    ['report.generate', 'execute'],
  ]);
  for (const [action, access] of required) {
    const capability = RUNTIME_CAPABILITIES.find((cap) => cap.action === action);
    assert(capability !== undefined, `${action} must be declared`);
    assert(capability.access === access, `${action} has unexpected access classification`);
    assert(capability.bound === false, `${action} must remain unbound`);
  }
});

Deno.test('capability diagnostics do not confuse queue persistence with provider authorization', () => {
  const diagnostics = capabilityDiagnostics();
  assert(diagnostics.length === RUNTIME_CAPABILITIES.length, 'every declared capability needs a diagnostic');
  for (const diagnostic of diagnostics) {
    assert(diagnostic.declared === true, 'capability must be explicitly declared');
    assert(diagnostic.bound === false, 'external provider binding must remain false');
    assert(diagnostic.authorization_state === 'not_bound', 'unbound capability must report not_bound');
    assert(diagnostic.authorized === false, 'unbound capability must not claim authorization');
    assert(diagnostic.verified === false, 'unbound capability must not claim verification');
    assert(diagnostic.last_error === null, 'unattempted capability must not invent an error');
  }
});

Deno.test('checkpoint create validates identity status fingerprint and secret boundary', () => {
  const fingerprint = `sha256-v1:${'a'.repeat(64)}`;
  const valid = validateCheckpointCreate({
    task: {
      schema_version: 'agent-task-v1', task_id: 'agent-checkpoint-create-test', title: 'test', goal: 'test',
      allowed_actions: ['github.read_main'], steps: [{ step_id: 'one', action: 'github.read_main' }],
    },
    state: {
      schema_version: 'agent-task-state-v1', task_id: 'agent-checkpoint-create-test',
      spec_fingerprint: fingerprint, status: 'pending',
    },
  });
  assert(valid.ok === true, 'valid checkpoint create should pass');
  if (valid.ok) assert(valid.idempotency_key === 'agent-checkpoint-create-test', 'task id should default idempotency key');

  const badStatus = validateCheckpointCreate({
    task: { schema_version: 'agent-task-v1', task_id: 'agent-checkpoint-create-test' },
    state: {
      schema_version: 'agent-task-state-v1', task_id: 'agent-checkpoint-create-test',
      spec_fingerprint: fingerprint, status: 'running',
    },
  });
  assert(badStatus.ok === false, 'new checkpoint must start pending');

  const secret = validateCheckpointCreate({
    task: { schema_version: 'agent-task-v1', task_id: 'agent-secret-test', inputs: { api_key: 'nope' } },
    state: {
      schema_version: 'agent-task-state-v1', task_id: 'agent-secret-test',
      spec_fingerprint: fingerprint, status: 'pending',
    },
  });
  assert(secret.ok === false, 'secret-shaped task input must be rejected');
});

Deno.test('checkpoint save requires CAS revision and matching durable state', () => {
  const fingerprint = `sha256-v1:${'b'.repeat(64)}`;
  const valid = validateCheckpointSave({
    task_id: 'agent-checkpoint-save-test', expected_revision: 3, status: 'blocked',
    state: {
      schema_version: 'agent-task-state-v1', task_id: 'agent-checkpoint-save-test',
      spec_fingerprint: fingerprint, status: 'blocked', blocked_reason: 'manual_auth_required',
    },
  });
  assert(valid.ok === true, 'valid checkpoint save should pass');

  const staleShape = validateCheckpointSave({
    task_id: 'agent-checkpoint-save-test', expected_revision: -1, status: 'blocked',
    state: {
      schema_version: 'agent-task-state-v1', task_id: 'agent-checkpoint-save-test',
      spec_fingerprint: fingerprint, status: 'blocked',
    },
  });
  assert(staleShape.ok === false, 'negative revisions must fail validation');
});

Deno.test('activity append/list keep secret and pagination boundaries', () => {
  const valid = validateActivityAppend({
    task_id: 'agent-activity-test', event_type: 'step_completed', step_id: 'step-1',
    payload: { attempt: 1, verified: true },
  });
  assert(valid.ok === true, 'valid activity event should pass');
  const secret = validateActivityAppend({
    task_id: 'agent-activity-test', event_type: 'provider_result',
    payload: { nested: { access_token: 'must-not-persist' } },
  });
  assert(secret.ok === false, 'secret-shaped activity payload must be rejected');
  if (!secret.ok && 'secret_path' in secret) {
    assert(secret.secret_path === '$.nested.access_token', 'secret path should be explicit');
  }
  assert(validateActivityList({ task_id: 'agent-activity-test', after_event_id: 7, limit: 200 }).ok === true, 'valid list request rejected');
  assert(validateActivityList({ task_id: 'agent-activity-test', after_event_id: -1 }).ok === false, 'negative cursor must fail');
  assert(validateActivityList({ task_id: 'agent-activity-test', limit: 201 }).ok === false, 'oversized page must fail');
});

Deno.test('queue claim validates worker identity and bounded lease duration', () => {
  assert(validateWorkerId('worker-1:host.a') === 'worker-1:host.a', 'valid worker id rejected');
  assert(validateWorkerId('../bad') === null, 'path-like worker id must fail');
  const valid = validateQueueClaim({ worker_id: 'worker-a', lease_seconds: 120 });
  assert(valid.ok === true, 'valid queue claim rejected');
  assert(validateQueueClaim({ worker_id: 'worker-a', lease_seconds: 5 }).ok === false, 'short lease must fail');
  assert(validateQueueClaim({ worker_id: 'worker-a', lease_seconds: 3601 }).ok === false, 'long lease must fail');
});

Deno.test('queue save requires revision worker fence generation state and lease duration', () => {
  const fingerprint = `sha256-v1:${'c'.repeat(64)}`;
  const valid = validateQueueSave({
    task_id: 'queue-save-test', expected_revision: 4, worker_id: 'worker-a', lease_generation: 2,
    lease_seconds: 120, status: 'running',
    state: {
      schema_version: 'agent-task-state-v1', task_id: 'queue-save-test',
      spec_fingerprint: fingerprint, status: 'running',
    },
  });
  assert(valid.ok === true, 'valid fenced queue save rejected');
  assert(validateQueueSave({
    task_id: 'queue-save-test', expected_revision: 4, worker_id: 'worker-a', lease_generation: 0,
    lease_seconds: 120, status: 'running',
    state: {
      schema_version: 'agent-task-state-v1', task_id: 'queue-save-test',
      spec_fingerprint: fingerprint, status: 'running',
    },
  }).ok === false, 'zero fencing generation must fail');
  assert(validateQueueSave({
    task_id: 'queue-save-test', expected_revision: 4, worker_id: 'worker-a', lease_generation: 2,
    lease_seconds: 120, status: 'running',
    state: {
      schema_version: 'agent-task-state-v1', task_id: 'queue-save-test',
      spec_fingerprint: fingerprint, status: 'running', nested: { password: 'nope' },
    },
  }).ok === false, 'secret-shaped queue state must fail');
});

Deno.test('expired lease reconciliation only accepts blocked state and a positive generation', () => {
  const fingerprint = `sha256-v1:${'d'.repeat(64)}`;
  const valid = validateQueueReconcileExpired({
    task_id: 'queue-expired-test', expected_revision: 7, lease_generation: 3,
    state: {
      schema_version: 'agent-task-state-v1', task_id: 'queue-expired-test',
      spec_fingerprint: fingerprint, status: 'blocked', blocked_reason: 'expired_lease_requires_reconciliation',
    },
  });
  assert(valid.ok === true, 'valid expired lease reconciliation rejected');
  assert(validateQueueReconcileExpired({
    task_id: 'queue-expired-test', expected_revision: 7, lease_generation: 3,
    state: {
      schema_version: 'agent-task-state-v1', task_id: 'queue-expired-test',
      spec_fingerprint: fingerprint, status: 'running',
    },
  }).ok === false, 'running state must not be accepted for expired reconciliation');
});

Deno.test('task id validation matches database format contract', () => {
  assert(validateTaskId('Task_1.ok-yes') === 'Task_1.ok-yes', 'valid task id rejected');
  assert(validateTaskId('../escape') === null, 'path-like task id must be rejected');
  assert(validateTaskId('') === null, 'empty task id must be rejected');
});

Deno.test('read-only task preflight remains blocked on missing provider bindings', () => {
  const task = {
    schema_version: 'agent-task-v1', task_id: 'keirin-read-status',
    allowed_actions: ['github.read_main', 'github.verify_ci'],
    steps: [{ step_id: 'read-main', action: 'github.read_main', verify_action: 'github.verify_ci' }],
  };
  const result = preflightTask(task, ['read']);
  assert(result.ok === true, 'task should pass structural preflight');
  assert(result.ready === false, 'unbound host capabilities must prevent ready=true');
  assert(result.forbidden_access_actions.length === 0, 'read-only task should not violate access policy');
  assert(result.unbound_actions.includes('github.read_main'), 'missing GitHub read binding must be reported');
  assert(result.execution_enabled === false, 'preflight must never enable task execution');
});

Deno.test('execute and write capabilities stay blocked under read-only policy', () => {
  const executeTask = {
    schema_version: 'agent-task-v1', task_id: 'image-generation-test',
    allowed_actions: ['image.generate'], steps: [{ step_id: 'generate', action: 'image.generate' }],
  };
  const executeResult = preflightTask(executeTask, ['read']);
  assert(executeResult.ok === true && executeResult.ready === false, 'execute task must remain blocked');
  assert(executeResult.forbidden_access_actions.includes('image.generate'), 'execute action must be forbidden');

  const writeTask = {
    schema_version: 'agent-task-v1', task_id: 'artifact-write-test',
    allowed_actions: ['files.write_artifact'], steps: [{ step_id: 'write', action: 'files.write_artifact' }],
  };
  const writeResult = preflightTask(writeTask, ['read']);
  assert(writeResult.ok === true && writeResult.ready === false, 'write task must remain blocked');
  assert(writeResult.forbidden_access_actions.includes('files.write_artifact'), 'write action must be forbidden');
});

Deno.test('task preflight rejects secret-shaped fields recursively', () => {
  const task = {
    schema_version: 'agent-task-v1', task_id: 'secret-test', allowed_actions: ['github.read_main'],
    inputs: { nested: { api_key: 'must-not-be-sent' } },
    steps: [{ step_id: 'read', action: 'github.read_main' }],
  };
  const path = findForbiddenSecretPath(task);
  assert(path === '$.inputs.nested.api_key', 'secret path should identify nested field');
  assert(preflightTask(task, ['read']).ok === false, 'task containing secret-shaped field must be rejected');
});

Deno.test('task preflight reports undeclared and unknown actions', () => {
  const task = {
    schema_version: 'agent-task-v1', task_id: 'bad-actions', allowed_actions: ['github.read_main'],
    steps: [
      { step_id: 'known-but-undeclared', action: 'github.verify_ci' },
      { step_id: 'unknown', action: 'provider.does_not_exist' },
    ],
  };
  const result = preflightTask(task, ['read']);
  assert(result.ok === true, 'structural preflight should return a detailed blocked result');
  assert(result.ready === false, 'undeclared/unknown actions must prevent ready state');
  assert(result.undeclared_actions.includes('github.verify_ci'), 'undeclared action should be reported');
  assert(result.unknown_actions.includes('provider.does_not_exist'), 'unknown action should be reported');
});
