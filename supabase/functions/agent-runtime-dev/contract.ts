export const AGENT_RUNTIME_SERVICE = 'agent-runtime-dev';
export const AGENT_RUNTIME_VERSION = 'v4-owner-checkpoint-persistence';
export const TASK_SCHEMA_VERSION = 'agent-task-v1';
export const TASK_STATE_SCHEMA_VERSION = 'agent-task-state-v1';
export const RUNTIME_BINDING_SCHEMA_VERSION = 'agent-runtime-bindings-v1';

export type AccessMode = 'read' | 'write' | 'execute';
export type AuthorizationState = 'not_bound' | 'not_configured' | 'authorized' | 'authorization_failed';

export type RuntimeCapability = {
  action: string;
  access: AccessMode;
  required_permissions: string[];
  bound: boolean;
  supports_dry_run: boolean;
  description: string;
};

export type CapabilityDiagnostic = {
  action: string;
  access: AccessMode;
  declared: true;
  bound: boolean;
  authorization_state: AuthorizationState;
  authorized: boolean;
  verified: boolean;
  last_error: string | null;
  supports_dry_run: boolean;
  required_permissions: string[];
};

export const SAFETY_STATE = Object.freeze({
  production_prediction_enabled: false,
  db_write_enabled: false,
  external_automatic_fetch_enabled: false,
  runtime_task_execution_enabled: false,
  persistence_enabled: true,
  checkpoint_persistence_scope: 'agent_only',
});

export const CHECKPOINT_MODES = Object.freeze([
  'checkpoint_create',
  'checkpoint_get',
  'checkpoint_list',
  'checkpoint_save',
]);

export const RUNTIME_CAPABILITIES: RuntimeCapability[] = [
  {
    action: 'github.read_main',
    access: 'read',
    required_permissions: ['contents:read'],
    bound: false,
    supports_dry_run: true,
    description: 'External host binding required. Read repository files only.',
  },
  {
    action: 'github.verify_ci',
    access: 'read',
    required_permissions: ['actions:read'],
    bound: false,
    supports_dry_run: true,
    description: 'External host binding required. Verify existing CI only.',
  },
  {
    action: 'supabase.project_status',
    access: 'read',
    required_permissions: ['supabase:project:read'],
    bound: false,
    supports_dry_run: true,
    description: 'External host binding required. Read project status only.',
  },
  {
    action: 'supabase.function_status',
    access: 'read',
    required_permissions: ['supabase:functions:read'],
    bound: false,
    supports_dry_run: true,
    description: 'External host binding required. Read function metadata only.',
  },
  {
    action: 'files.read_artifact',
    access: 'read',
    required_permissions: ['files:read'],
    bound: false,
    supports_dry_run: true,
    description: 'External host binding required. Read an explicit private artifact.',
  },
  {
    action: 'files.verify_artifact',
    access: 'read',
    required_permissions: ['files:read'],
    bound: false,
    supports_dry_run: true,
    description: 'External host binding required. Verify an explicit private artifact.',
  },
  {
    action: 'files.write_artifact',
    access: 'write',
    required_permissions: ['files:write'],
    bound: false,
    supports_dry_run: false,
    description: 'External host binding required. No file-write binding is enabled in v4.',
  },
  {
    action: 'research.read_public_sources',
    access: 'read',
    required_permissions: ['research:read'],
    bound: false,
    supports_dry_run: true,
    description: 'Read public research sources through a separately authorized host binding.',
  },
  {
    action: 'text.generate',
    access: 'execute',
    required_permissions: ['text:generate'],
    bound: false,
    supports_dry_run: false,
    description: 'Generate or transform text through a separately authorized model provider.',
  },
  {
    action: 'image.generate',
    access: 'execute',
    required_permissions: ['image:generate'],
    bound: false,
    supports_dry_run: false,
    description: 'Generate or edit images through a separately authorized image provider.',
  },
  {
    action: 'video.generate',
    access: 'execute',
    required_permissions: ['video:generate'],
    bound: false,
    supports_dry_run: false,
    description: 'Generate video through a separately authorized video provider.',
  },
  {
    action: 'code.generate',
    access: 'execute',
    required_permissions: ['code:generate'],
    bound: false,
    supports_dry_run: false,
    description: 'Generate program text without applying repository writes by itself.',
  },
  {
    action: 'learning.evaluate',
    access: 'execute',
    required_permissions: ['learning:evaluate'],
    bound: false,
    supports_dry_run: true,
    description: 'Evaluate models or tasks using explicit inputs and verification criteria.',
  },
  {
    action: 'report.generate',
    access: 'execute',
    required_permissions: ['report:generate'],
    bound: false,
    supports_dry_run: true,
    description: 'Generate a report from available state without delivering it.',
  },
  {
    action: 'report.deliver',
    access: 'write',
    required_permissions: ['report:deliver'],
    bound: false,
    supports_dry_run: false,
    description: 'Destination is intentionally not configured in v4.',
  },
];

export function capabilityDiagnostics(): CapabilityDiagnostic[] {
  return RUNTIME_CAPABILITIES.map((capability) => ({
    action: capability.action,
    access: capability.access,
    declared: true as const,
    bound: capability.bound,
    authorization_state: capability.bound ? 'not_configured' : 'not_bound',
    authorized: false,
    verified: false,
    last_error: null,
    supports_dry_run: capability.supports_dry_run,
    required_permissions: [...capability.required_permissions],
  }));
}

const FORBIDDEN_SECRET_KEYS = new Set([
  'token',
  'access_token',
  'refresh_token',
  'password',
  'secret',
  'service_role',
  'service_role_key',
  'api_key',
  'apikey',
  'authorization',
]);

const TASK_ID_RE = /^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$/;
const FINGERPRINT_RE = /^sha256-v1:[0-9a-f]{64}$/;
const SAVE_STATUSES = new Set(['running', 'blocked', 'completed', 'failed']);

export function findForbiddenSecretPath(value: unknown, path = '$'): string | null {
  if (!value || typeof value !== 'object') return null;
  if (Array.isArray(value)) {
    for (let i = 0; i < value.length; i += 1) {
      const found = findForbiddenSecretPath(value[i], `${path}[${i}]`);
      if (found) return found;
    }
    return null;
  }
  for (const [key, child] of Object.entries(value as Record<string, unknown>)) {
    if (FORBIDDEN_SECRET_KEYS.has(key.toLowerCase())) return `${path}.${key}`;
    const found = findForbiddenSecretPath(child, `${path}.${key}`);
    if (found) return found;
  }
  return null;
}

function asObject(value: unknown): Record<string, unknown> | null {
  return value && typeof value === 'object' && !Array.isArray(value)
    ? value as Record<string, unknown>
    : null;
}

function asStringArray(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === 'string') : [];
}

function taskActions(task: Record<string, unknown>): string[] {
  const steps = Array.isArray(task.steps) ? task.steps : [];
  const actions: string[] = [];
  for (const raw of steps) {
    if (!raw || typeof raw !== 'object' || Array.isArray(raw)) continue;
    const step = raw as Record<string, unknown>;
    if (typeof step.action === 'string') actions.push(step.action);
    if (typeof step.verify_action === 'string') actions.push(step.verify_action);
  }
  return [...new Set(actions)];
}

export function validateTaskId(value: unknown): string | null {
  return typeof value === 'string' && TASK_ID_RE.test(value) ? value : null;
}

export function validateCheckpointCreate(input: unknown) {
  const body = asObject(input);
  if (!body) return { ok: false, error: 'request must be an object' } as const;
  const task = asObject(body.task);
  const state = asObject(body.state);
  if (!task || !state) return { ok: false, error: 'task and state are required objects' } as const;
  const secretPath = findForbiddenSecretPath({ task, state });
  if (secretPath) return { ok: false, error: 'checkpoint contains a forbidden secret field', secret_path: secretPath } as const;
  if (task.schema_version !== TASK_SCHEMA_VERSION) return { ok: false, error: 'task schema mismatch' } as const;
  if (state.schema_version !== TASK_STATE_SCHEMA_VERSION) return { ok: false, error: 'state schema mismatch' } as const;
  const taskId = validateTaskId(task.task_id);
  if (!taskId || state.task_id !== taskId) return { ok: false, error: 'task/state task_id mismatch' } as const;
  if (state.status !== 'pending') return { ok: false, error: 'new checkpoint state must be pending' } as const;
  const fingerprint = typeof state.spec_fingerprint === 'string' ? state.spec_fingerprint : '';
  if (!FINGERPRINT_RE.test(fingerprint)) return { ok: false, error: 'valid state spec_fingerprint is required' } as const;
  const idempotencyKey = typeof body.idempotency_key === 'string' && body.idempotency_key.trim()
    ? body.idempotency_key.trim()
    : taskId;
  if (idempotencyKey.length > 200) return { ok: false, error: 'idempotency_key too long' } as const;
  return { ok: true, task_id: taskId, idempotency_key: idempotencyKey, task, state, spec_fingerprint: fingerprint } as const;
}

export function validateCheckpointSave(input: unknown) {
  const body = asObject(input);
  if (!body) return { ok: false, error: 'request must be an object' } as const;
  const taskId = validateTaskId(body.task_id);
  const state = asObject(body.state);
  if (!taskId || !state) return { ok: false, error: 'valid task_id and state are required' } as const;
  if (findForbiddenSecretPath(state)) return { ok: false, error: 'state contains a forbidden secret field' } as const;
  if (state.schema_version !== TASK_STATE_SCHEMA_VERSION || state.task_id !== taskId) {
    return { ok: false, error: 'state identity/schema mismatch' } as const;
  }
  const status = typeof body.status === 'string' ? body.status : '';
  if (!SAVE_STATUSES.has(status) || state.status !== status) return { ok: false, error: 'status/state mismatch' } as const;
  const fingerprint = typeof state.spec_fingerprint === 'string' ? state.spec_fingerprint : '';
  if (!FINGERPRINT_RE.test(fingerprint)) return { ok: false, error: 'valid state spec_fingerprint is required' } as const;
  const revision = body.expected_revision;
  if (!Number.isSafeInteger(revision) || (revision as number) < 0) {
    return { ok: false, error: 'expected_revision must be a non-negative safe integer' } as const;
  }
  return { ok: true, task_id: taskId, status, state, expected_revision: revision as number } as const;
}

export function preflightTask(taskInput: unknown, allowedAccessInput: unknown = ['read']) {
  if (!taskInput || typeof taskInput !== 'object' || Array.isArray(taskInput)) {
    return { ok: false, error: 'task must be an object' } as const;
  }
  const secretPath = findForbiddenSecretPath(taskInput);
  if (secretPath) {
    return { ok: false, error: 'task contains a forbidden secret field', secret_path: secretPath } as const;
  }
  const task = taskInput as Record<string, unknown>;
  if (task.schema_version !== TASK_SCHEMA_VERSION) {
    return { ok: false, error: 'task schema mismatch' } as const;
  }
  if (!validateTaskId(task.task_id)) {
    return { ok: false, error: 'valid task_id is required' } as const;
  }
  const allowedActions = new Set(asStringArray(task.allowed_actions));
  const usedActions = taskActions(task);
  if (usedActions.length === 0) {
    return { ok: false, error: 'task has no executable actions' } as const;
  }
  const undeclared = usedActions.filter((action) => !allowedActions.has(action));
  const capabilityByAction = new Map(RUNTIME_CAPABILITIES.map((cap) => [cap.action, cap]));
  const unknownActions = usedActions.filter((action) => !capabilityByAction.has(action));
  const allowedAccess = new Set(asStringArray(allowedAccessInput));
  const forbiddenAccess = usedActions.filter((action) => {
    const cap = capabilityByAction.get(action);
    return cap ? !allowedAccess.has(cap.access) : false;
  });
  const unboundActions = usedActions.filter((action) => capabilityByAction.get(action)?.bound === false);
  const ready = undeclared.length === 0 && unknownActions.length === 0 && forbiddenAccess.length === 0 && unboundActions.length === 0;
  return {
    ok: true,
    task_id: task.task_id,
    ready,
    execution_enabled: false,
    used_actions: usedActions,
    undeclared_actions: undeclared,
    unknown_actions: unknownActions,
    forbidden_access_actions: forbiddenAccess,
    unbound_actions: unboundActions,
    safety: SAFETY_STATE,
  } as const;
}
