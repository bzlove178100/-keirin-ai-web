export const AGENT_RUNTIME_SERVICE = 'agent-runtime-dev';
export const AGENT_RUNTIME_VERSION = 'v1-owner-readonly-preflight';
export const TASK_SCHEMA_VERSION = 'agent-task-v1';
export const RUNTIME_BINDING_SCHEMA_VERSION = 'agent-runtime-bindings-v1';

export type AccessMode = 'read' | 'write' | 'execute';

export type RuntimeCapability = {
  action: string;
  access: AccessMode;
  required_permissions: string[];
  bound: boolean;
  supports_dry_run: boolean;
  description: string;
};

export const SAFETY_STATE = Object.freeze({
  production_prediction_enabled: false,
  db_write_enabled: false,
  external_automatic_fetch_enabled: false,
  runtime_task_execution_enabled: false,
  persistence_enabled: false,
});

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
    description: 'External host binding required. No write binding is enabled in v1.',
  },
  {
    action: 'report.deliver',
    access: 'write',
    required_permissions: ['report:deliver'],
    bound: false,
    supports_dry_run: false,
    description: 'Destination is intentionally not configured in v1.',
  },
];

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
  if (typeof task.task_id !== 'string' || !task.task_id.trim()) {
    return { ok: false, error: 'task_id is required' } as const;
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
