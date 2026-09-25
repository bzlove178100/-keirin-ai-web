import {
  AGENT_RUNTIME_VERSION,
  RUNTIME_CAPABILITIES,
  SAFETY_STATE,
  capabilityDiagnostics,
  findForbiddenSecretPath,
  preflightTask,
} from '../supabase/functions/agent-runtime-dev/contract.ts';

function assert(condition: unknown, message: string): asserts condition {
  if (!condition) throw new Error(message);
}

Deno.test('hosted agent runtime version exposes general capability contracts', () => {
  assert(
    AGENT_RUNTIME_VERSION === 'v3-owner-preflight-general-capability-contracts',
    'runtime version changed unexpectedly',
  );
});

Deno.test('hosted agent runtime keeps all side-effect switches disabled', () => {
  assert(SAFETY_STATE.production_prediction_enabled === false, 'production prediction must remain off');
  assert(SAFETY_STATE.db_write_enabled === false, 'database writing must remain off');
  assert(SAFETY_STATE.external_automatic_fetch_enabled === false, 'external automatic fetching must remain off');
  assert(SAFETY_STATE.runtime_task_execution_enabled === false, 'runtime task execution must remain off in v3');
  assert(SAFETY_STATE.persistence_enabled === false, 'hosted task persistence must remain off in v3');
});

Deno.test('all external capabilities start explicitly unbound', () => {
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

Deno.test('capability diagnostics distinguish declared bound authorized verified and last error', () => {
  const diagnostics = capabilityDiagnostics();
  assert(diagnostics.length === RUNTIME_CAPABILITIES.length, 'every declared capability needs a diagnostic');
  for (const diagnostic of diagnostics) {
    assert(diagnostic.declared === true, 'capability must be explicitly declared');
    assert(diagnostic.bound === false, 'hosted v3 has no provider binding');
    assert(diagnostic.authorization_state === 'not_bound', 'unbound capability must report not_bound authorization state');
    assert(diagnostic.authorized === false, 'unbound capability must not claim authorization');
    assert(diagnostic.verified === false, 'unbound capability must not claim verification');
    assert(diagnostic.last_error === null, 'unattempted capability must not invent an error');
  }
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
    inputs: {
      nested: {
        api_key: 'must-not-be-sent',
      },
    },
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
