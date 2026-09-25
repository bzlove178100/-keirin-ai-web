import {
  ACTIVITY_MODES,
  AGENT_RUNTIME_VERSION,
  CHECKPOINT_MODES,
  RUNTIME_CAPABILITIES,
  SAFETY_STATE,
  capabilityDiagnostics,
  findForbiddenSecretPath,
  preflightTask,
  validateActivityAppend,
  validateActivityList,
  validateCheckpointCreate,
  validateCheckpointSave,
  validateTaskId,
} from '../supabase/functions/agent-runtime-dev/contract.ts';

function assert(condition: unknown, message: string): asserts condition {
  if (!condition) throw new Error(message);
}

Deno.test('hosted agent runtime version enables owner checkpoint and activity persistence only', () => {
  assert(
    AGENT_RUNTIME_VERSION === 'v5-owner-checkpoint-activity-persistence',
    'runtime version changed unexpectedly',
  );
  assert(SAFETY_STATE.production_prediction_enabled === false, 'production prediction must remain off');
  assert(SAFETY_STATE.db_write_enabled === false, 'keirin database writing must remain off');
  assert(SAFETY_STATE.external_automatic_fetch_enabled === false, 'external automatic fetching must remain off');
  assert(SAFETY_STATE.runtime_task_execution_enabled === false, 'runtime task execution must remain off in v5');
  assert(SAFETY_STATE.persistence_enabled === true, 'agent checkpoint persistence must remain enabled');
  assert(SAFETY_STATE.checkpoint_persistence_scope === 'agent_only', 'persistence scope must remain agent-only');
  assert(SAFETY_STATE.activity_persistence_enabled === true, 'append-only agent activity persistence must be enabled');
});

Deno.test('persistence modes are explicit and do not include task execution', () => {
  const checkpoints = ['checkpoint_create', 'checkpoint_get', 'checkpoint_list', 'checkpoint_save'];
  assert(checkpoints.every((mode) => CHECKPOINT_MODES.includes(mode as never)), 'checkpoint modes missing');
  assert(ACTIVITY_MODES.includes('event_append'), 'event_append mode missing');
  assert(ACTIVITY_MODES.includes('event_list'), 'event_list mode missing');
  assert(!CHECKPOINT_MODES.includes('execute' as never), 'checkpoint modes must not enable task execution');
  assert(!ACTIVITY_MODES.includes('execute' as never), 'activity modes must not enable task execution');
});

Deno.test('all external provider capabilities remain explicitly unbound', () => {
  assert(RUNTIME_CAPABILITIES.length >= 13, 'expected shared runtime capability declarations');
  assert(RUNTIME_CAPABILITIES.every((cap) => cap.bound === false), 'no provider capability may be silently bound');
  const delivery = RUNTIME_CAPABILITIES.find((cap) => cap.action === 'report.deliver');
  assert(delivery?.access === 'write', 'report delivery must be classified as a write');
  assert(delivery?.supports_dry_run === false, 'report delivery must not pretend to support dry-run');
});

Deno.test('broad agent capabilities are declared but not authorized or enabled', () => {
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

Deno.test('capability diagnostics do not confuse agent persistence with provider authorization', () => {
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
      schema_version: 'agent-task-v1',
      task_id: 'agent-checkpoint-create-test',
      title: 'test',
      goal: 'test',
      allowed_actions: ['github.read_main'],
      steps: [{ step_id: 'one', action: 'github.read_main' }],
    },
    state: {
      schema_version: 'agent-task-state-v1',
      task_id: 'agent-checkpoint-create-test',
      spec_fingerprint: fingerprint,
      status: 'pending',
    },
  });
  assert(valid.ok === true, 'valid checkpoint create should pass');
  if (valid.ok) assert(valid.idempotency_key === 'agent-checkpoint-create-test', 'task id should default idempotency key');

  const badStatus = validateCheckpointCreate({
    task: { schema_version: 'agent-task-v1', task_id: 'agent-checkpoint-create-test' },
    state: {
      schema_version: 'agent-task-state-v1',
      task_id: 'agent-checkpoint-create-test',
      spec_fingerprint: fingerprint,
      status: 'running',
    },
  });
  assert(badStatus.ok === false, 'new checkpoint must start pending');

  const secret = validateCheckpointCreate({
    task: { schema_version: 'agent-task-v1', task_id: 'agent-secret-test', inputs: { api_key: 'nope' } },
    state: {
      schema_version: 'agent-task-state-v1',
      task_id: 'agent-secret-test',
      spec_fingerprint: fingerprint,
      status: 'pending',
    },
  });
  assert(secret.ok === false, 'secret-shaped task input must be rejected');
});

Deno.test('checkpoint save requires CAS revision and matching durable state', () => {
  const fingerprint = `sha256-v1:${'b'.repeat(64)}`;
  const valid = validateCheckpointSave({
    task_id: 'agent-checkpoint-save-test',
    expected_revision: 3,
    status: 'blocked',
    state: {
      schema_version: 'agent-task-state-v1',
      task_id: 'agent-checkpoint-save-test',
      spec_fingerprint: fingerprint,
      status: 'blocked',
      blocked_reason: 'manual_auth_required',
    },
  });
  assert(valid.ok === true, 'valid checkpoint save should pass');

  const staleShape = validateCheckpointSave({
    task_id: 'agent-checkpoint-save-test',
    expected_revision: -1,
    status: 'blocked',
    state: {
      schema_version: 'agent-task-state-v1',
      task_id: 'agent-checkpoint-save-test',
      spec_fingerprint: fingerprint,
      status: 'blocked',
    },
  });
  assert(staleShape.ok === false, 'negative revisions must fail validation');

  const mismatch = validateCheckpointSave({
    task_id: 'agent-checkpoint-save-test',
    expected_revision: 3,
    status: 'completed',
    state: {
      schema_version: 'agent-task-state-v1',
      task_id: 'agent-checkpoint-save-test',
      spec_fingerprint: fingerprint,
      status: 'running',
    },
  });
  assert(mismatch.ok === false, 'status mismatch must fail validation');
});

Deno.test('activity append validates task/event identity and rejects secret-shaped payloads', () => {
  const valid = validateActivityAppend({
    task_id: 'agent-activity-test',
    event_type: 'step_completed',
    step_id: 'step-1',
    payload: { attempt: 1, verified: true },
  });
  assert(valid.ok === true, 'valid activity event should pass');
  if (valid.ok) {
    assert(valid.event_type === 'step_completed', 'event type should be normalized');
    assert(valid.step_id === 'step-1', 'step id should be normalized');
  }

  const secret = validateActivityAppend({
    task_id: 'agent-activity-test',
    event_type: 'provider_result',
    payload: { nested: { access_token: 'must-not-persist' } },
  });
  assert(secret.ok === false, 'secret-shaped activity payload must be rejected');
  if (!secret.ok && 'secret_path' in secret) {
    assert(secret.secret_path === '$.nested.access_token', 'secret path should be explicit');
  }

  const badStep = validateActivityAppend({
    task_id: 'agent-activity-test',
    event_type: 'x',
    step_id: ' ',
    payload: {},
  });
  assert(badStep.ok === false, 'blank activity step id must fail');
});

Deno.test('activity list validates cursor and bounded page size', () => {
  const valid = validateActivityList({ task_id: 'agent-activity-test', after_event_id: 7, limit: 200 });
  assert(valid.ok === true, 'valid activity list request should pass');
  if (valid.ok) {
    assert(valid.after_event_id === 7, 'activity cursor should be preserved');
    assert(valid.limit === 200, 'activity list limit should be preserved');
  }
  assert(validateActivityList({ task_id: 'agent-activity-test', after_event_id: -1 }).ok === false, 'negative cursor must fail');
  assert(validateActivityList({ task_id: 'agent-activity-test', limit: 201 }).ok === false, 'oversized activity page must fail');
});

Deno.test('task id validation matches database format contract', () => {
  assert(validateTaskId('Task_1.ok-yes') === 'Task_1.ok-yes', 'valid task id rejected');
  assert(validateTaskId('../escape') === null, 'path-like task id must be rejected');
  assert(validateTaskId('') === null, 'empty task id must be rejected');
});

Deno.test('read-only task preflight is valid but blocked on missing host bindings', () => {
  const task = {
    schema_version: 'agent-task-v1',
    task_id: 'keirin-read-status',
    allowed_actions: ['github.read_main', 'github.verify_ci'],
    steps: [
      {
        step_id: 'read-main',
        action: 'github.read_main',
        verify_action: 'github.verify_ci',
      },
    ],
  };
  const result = preflightTask(task, ['read']);
  assert(result.ok === true, 'task should pass structural preflight');
  assert(result.ready === false, 'unbound host capabilities must prevent ready=true');
  assert(result.forbidden_access_actions.length === 0, 'read-only task should not violate access policy');
  assert(result.unbound_actions.includes('github.read_main'), 'missing GitHub read binding must be reported');
  assert(result.unbound_actions.includes('github.verify_ci'), 'missing CI binding must be reported');
  assert(result.execution_enabled === false, 'preflight must never enable task execution');
});

Deno.test('execute capability stays blocked when only read access is allowed', () => {
  const task = {
    schema_version: 'agent-task-v1',
    task_id: 'image-generation-test',
    allowed_actions: ['image.generate'],
    steps: [{ step_id: 'generate', action: 'image.generate' }],
  };
  const result = preflightTask(task, ['read']);
  assert(result.ok === true, 'task should pass structural validation');
  assert(result.ready === false, 'execute action must not be ready under read-only policy');
  assert(result.forbidden_access_actions.includes('image.generate'), 'execute action must be reported as forbidden');
  assert(result.unbound_actions.includes('image.generate'), 'unbound generation provider must be reported');
});

Deno.test('preflight blocks write capability under read-only access policy', () => {
  const task = {
    schema_version: 'agent-task-v1',
    task_id: 'artifact-write-test',
    allowed_actions: ['files.write_artifact'],
    steps: [{ step_id: 'write', action: 'files.write_artifact' }],
  };
  const result = preflightTask(task, ['read']);
  assert(result.ok === true, 'task should pass structural validation');
  assert(result.ready === false, 'write action must not be ready under read-only policy');
  assert(result.forbidden_access_actions.includes('files.write_artifact'), 'write action must be reported as forbidden');
});

Deno.test('task preflight rejects secret-shaped fields recursively', () => {
  const task = {
    schema_version: 'agent-task-v1',
    task_id: 'secret-test',
    allowed_actions: ['github.read_main'],
    inputs: { nested: { api_key: 'must-not-be-sent' } },
    steps: [{ step_id: 'read', action: 'github.read_main' }],
  };
  const path = findForbiddenSecretPath(task);
  assert(path === '$.inputs.nested.api_key', 'secret path should identify nested field');
  const result = preflightTask(task, ['read']);
  assert(result.ok === false, 'task containing secret-shaped field must be rejected');
});

Deno.test('task preflight rejects undeclared and unknown actions', () => {
  const task = {
    schema_version: 'agent-task-v1',
    task_id: 'bad-actions',
    allowed_actions: ['github.read_main'],
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
