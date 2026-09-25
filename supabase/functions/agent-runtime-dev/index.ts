import 'jsr:@supabase/functions-js/edge-runtime.d.ts';
import {
  ACTIVITY_MODES,
  AGENT_RUNTIME_SERVICE,
  AGENT_RUNTIME_VERSION,
  CHECKPOINT_MODES,
  RUNTIME_BINDING_SCHEMA_VERSION,
  RUNTIME_CAPABILITIES,
  SAFETY_STATE,
  capabilityDiagnostics,
  preflightTask,
  validateActivityAppend,
  validateActivityList,
  validateCheckpointCreate,
  validateCheckpointSave,
  validateTaskId,
} from './contract.ts';

const ALLOWED_ORIGIN = 'https://bzlove178100.github.io';
const CHECKPOINT_SELECT = [
  'task_id',
  'schema_version',
  'status',
  'idempotency_key',
  'spec',
  'state',
  'blocked_reason',
  'last_error',
  'revision',
  'spec_fingerprint',
  'created_at',
  'updated_at',
].join(',');
const CHECKPOINT_LIST_SELECT = [
  'task_id',
  'status',
  'revision',
  'idempotency_key',
  'blocked_reason',
  'last_error',
  'created_at',
  'updated_at',
].join(',');
const EVENT_SELECT = 'event_id,task_id,event_type,step_id,payload,created_at';
const CHECKPOINT_STATUSES = new Set(['queued', 'running', 'blocked', 'completed', 'failed']);

type OwnerContext = {
  ok: true;
  role: 'owner';
  plan: 'owner';
  userId: string;
  url: string;
  key: string;
};

type OwnerFailure = {
  ok: false;
  status: number;
  error: string;
};

function headersFor(origin: string) {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json; charset=utf-8',
    'Cache-Control': 'no-store',
    'X-Content-Type-Options': 'nosniff',
    'Vary': 'Origin',
    'Access-Control-Allow-Headers': 'authorization, apikey, content-type',
    'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
  };
  if (origin === ALLOWED_ORIGIN) headers['Access-Control-Allow-Origin'] = ALLOWED_ORIGIN;
  return headers;
}

function providerHeaders(owner: OwnerContext, authHeader: string, prefer?: string) {
  return {
    apikey: owner.key,
    Authorization: authHeader,
    Accept: 'application/json',
    'Content-Type': 'application/json',
    ...(prefer ? { Prefer: prefer } : {}),
  };
}

async function readJson(response: Response): Promise<unknown> {
  const text = await response.text();
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch (_) {
    return { message: text.slice(0, 500) };
  }
}

function persistenceError(data: unknown, status: number) {
  const body = data && typeof data === 'object' && !Array.isArray(data)
    ? data as Record<string, unknown>
    : {};
  const code = typeof body.code === 'string' ? body.code : null;
  const message = typeof body.message === 'string' ? body.message : 'Persistence request failed';
  return { success: false, error: message, backend_status: status, ...(code ? { backend_code: code } : {}) };
}

async function verifyOwner(authHeader: string): Promise<OwnerContext | OwnerFailure> {
  const url = Deno.env.get('SUPABASE_URL') ?? '';
  let key = '';
  try {
    const raw = Deno.env.get('SUPABASE_PUBLISHABLE_KEYS');
    if (raw) key = JSON.parse(raw).default ?? '';
  } catch (_) {
    // Fall back to legacy anon key below.
  }
  if (!key) key = Deno.env.get('SUPABASE_ANON_KEY') ?? '';
  if (!url || !key) return { ok: false, status: 500, error: 'Server configuration error' };

  const userRes = await fetch(`${url}/auth/v1/user`, {
    headers: { apikey: key, Authorization: authHeader },
  });
  if (!userRes.ok) return { ok: false, status: 401, error: 'Invalid or expired session' };
  const user = await userRes.json();
  if (!user?.id) return { ok: false, status: 401, error: 'User could not be verified' };

  const profileRes = await fetch(
    `${url}/rest/v1/user_profiles?user_id=eq.${encodeURIComponent(user.id)}&select=role,plan`,
    { headers: { apikey: key, Authorization: authHeader, Accept: 'application/json' } },
  );
  if (!profileRes.ok) return { ok: false, status: 403, error: 'Profile lookup failed' };
  const rows = await profileRes.json();
  const profile = Array.isArray(rows) && rows.length === 1 ? rows[0] : null;
  if (profile?.role !== 'owner' || profile?.plan !== 'owner') {
    return { ok: false, status: 403, error: 'Owner access required' };
  }
  return { ok: true, role: 'owner', plan: 'owner', userId: user.id, url, key };
}

async function checkpointPersistenceHealth(owner: OwnerContext, authHeader: string) {
  const response = await fetch(
    `${owner.url}/rest/v1/agent_tasks?select=task_id&limit=0`,
    { headers: providerHeaders(owner, authHeader) },
  );
  return response.ok;
}

async function activityPersistenceHealth(owner: OwnerContext, authHeader: string) {
  const response = await fetch(
    `${owner.url}/rest/v1/agent_task_events?select=event_id&limit=0`,
    { headers: providerHeaders(owner, authHeader) },
  );
  return response.ok;
}

async function getCheckpoint(owner: OwnerContext, authHeader: string, taskId: string) {
  const response = await fetch(
    `${owner.url}/rest/v1/agent_tasks?task_id=eq.${encodeURIComponent(taskId)}&select=${encodeURIComponent(CHECKPOINT_SELECT)}&limit=1`,
    { headers: providerHeaders(owner, authHeader) },
  );
  const data = await readJson(response);
  if (!response.ok) return { ok: false as const, status: response.status, data };
  const rows = Array.isArray(data) ? data : [];
  return { ok: true as const, row: rows.length === 1 ? rows[0] : null };
}

async function getActivityEvent(owner: OwnerContext, authHeader: string, taskId: string, eventId: number) {
  const response = await fetch(
    `${owner.url}/rest/v1/agent_task_events?task_id=eq.${encodeURIComponent(taskId)}&event_id=eq.${eventId}&select=${encodeURIComponent(EVENT_SELECT)}&limit=1`,
    { headers: providerHeaders(owner, authHeader) },
  );
  const data = await readJson(response);
  if (!response.ok) return { ok: false as const, status: response.status, data };
  const rows = Array.isArray(data) ? data : [];
  return { ok: true as const, row: rows.length === 1 ? rows[0] : null };
}

Deno.serve(async (req: Request) => {
  const origin = req.headers.get('Origin') ?? '';
  const headers = headersFor(origin);
  const reply = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers });

  if (origin && origin !== ALLOWED_ORIGIN) return reply({ success: false, error: 'Origin not allowed' }, 403);
  if (req.method === 'OPTIONS') return new Response('ok', { headers });
  if (!['GET', 'POST'].includes(req.method)) return reply({ success: false, error: 'Method not allowed' }, 405);

  const auth = req.headers.get('Authorization') ?? '';
  if (!auth.startsWith('Bearer ')) {
    return reply({ success: false, authenticated: false, error: 'Authentication required' }, 401);
  }
  const owner = await verifyOwner(auth);
  if (!owner.ok) {
    return reply(
      { success: false, authenticated: owner.status !== 401, owner: false, error: owner.error },
      owner.status,
    );
  }

  const [checkpointVerified, activityVerified] = await Promise.all([
    checkpointPersistenceHealth(owner, auth),
    activityPersistenceHealth(owner, auth),
  ]);
  const diagnostics = capabilityDiagnostics();
  const base = {
    success: true,
    service: AGENT_RUNTIME_SERVICE,
    service_version: AGENT_RUNTIME_VERSION,
    runtime_binding_schema: RUNTIME_BINDING_SCHEMA_VERSION,
    authenticated: true,
    owner: true,
    role: owner.role,
    plan: owner.plan,
    safety: SAFETY_STATE,
    checkpoint_modes: CHECKPOINT_MODES,
    activity_modes: ACTIVITY_MODES,
    capabilities: RUNTIME_CAPABILITIES,
    diagnostics: {
      runtime_mode: 'owner_checkpoint_activity_persistence',
      execution_enabled: false,
      persistence_enabled: true,
      persistence_verified: checkpointVerified,
      activity_persistence_verified: activityVerified,
      capability_status: diagnostics,
    },
    message:
      'Owner-only hosted runtime. Agent checkpoint and append-only activity persistence are enabled; task execution, provider writes, automatic keirin race-data fetching, and report delivery remain disabled.',
  };

  if (req.method === 'GET') return reply(base);

  let body: unknown;
  try {
    body = await req.json();
  } catch (_) {
    return reply({ success: false, error: 'Invalid JSON body' }, 400);
  }
  if (!body || typeof body !== 'object' || Array.isArray(body)) {
    return reply({ success: false, error: 'Request body must be an object' }, 400);
  }
  const requestBody = body as Record<string, unknown>;
  const mode = typeof requestBody.mode === 'string' ? requestBody.mode : '';

  if (mode === 'preflight') {
    const result = preflightTask(requestBody.task, requestBody.allowed_access ?? ['read']);
    if (!result.ok) {
      return reply(
        {
          success: false,
          service: AGENT_RUNTIME_SERVICE,
          service_version: AGENT_RUNTIME_VERSION,
          mode,
          error: result.error,
          ...('secret_path' in result ? { secret_path: result.secret_path } : {}),
          safety: SAFETY_STATE,
          diagnostics: base.diagnostics,
        },
        422,
      );
    }
    return reply({ ...base, mode, preflight: result, executed: false, saved: false, state_persisted: false });
  }

  if (CHECKPOINT_MODES.includes(mode as never) && !checkpointVerified) {
    return reply({ ...base, success: false, mode, error: 'Agent checkpoint storage is unavailable' }, 503);
  }
  if (ACTIVITY_MODES.includes(mode as never) && !activityVerified) {
    return reply({ ...base, success: false, mode, error: 'Agent activity storage is unavailable' }, 503);
  }

  if (mode === 'checkpoint_create') {
    const valid = validateCheckpointCreate(requestBody);
    if (!valid.ok) {
      return reply({ ...base, success: false, mode, error: valid.error, ...('secret_path' in valid ? { secret_path: valid.secret_path } : {}) }, 422);
    }
    const response = await fetch(`${owner.url}/rest/v1/rpc/agent_create_checkpoint`, {
      method: 'POST',
      headers: providerHeaders(owner, auth),
      body: JSON.stringify({
        p_task_id: valid.task_id,
        p_idempotency_key: valid.idempotency_key,
        p_spec: valid.task,
        p_state: valid.state,
        p_spec_fingerprint: valid.spec_fingerprint,
      }),
    });
    const data = await readJson(response);
    if (!response.ok) return reply({ ...base, ...persistenceError(data, response.status), mode }, response.status);
    return reply({ ...base, mode, checkpoint: data, saved: true, state_persisted: true }, 201);
  }

  if (mode === 'checkpoint_get') {
    const taskId = validateTaskId(requestBody.task_id);
    if (!taskId) return reply({ ...base, success: false, mode, error: 'valid task_id is required' }, 422);
    const result = await getCheckpoint(owner, auth, taskId);
    if (!result.ok) return reply({ ...base, ...persistenceError(result.data, result.status), mode }, result.status);
    if (!result.row) return reply({ ...base, success: false, mode, error: 'Checkpoint not found' }, 404);
    return reply({ ...base, mode, checkpoint: result.row, state_persisted: true });
  }

  if (mode === 'checkpoint_list') {
    const status = typeof requestBody.status === 'string' ? requestBody.status : '';
    if (status && !CHECKPOINT_STATUSES.has(status)) {
      return reply({ ...base, success: false, mode, error: 'invalid checkpoint status' }, 422);
    }
    const requestedLimit = Number(requestBody.limit ?? 20);
    const limit = Number.isSafeInteger(requestedLimit) ? Math.min(Math.max(requestedLimit, 1), 100) : 20;
    const statusFilter = status ? `&status=eq.${encodeURIComponent(status)}` : '';
    const response = await fetch(
      `${owner.url}/rest/v1/agent_tasks?select=${encodeURIComponent(CHECKPOINT_LIST_SELECT)}${statusFilter}&order=updated_at.desc&limit=${limit}`,
      { headers: providerHeaders(owner, auth) },
    );
    const data = await readJson(response);
    if (!response.ok) return reply({ ...base, ...persistenceError(data, response.status), mode }, response.status);
    return reply({ ...base, mode, checkpoints: Array.isArray(data) ? data : [], state_persisted: true });
  }

  if (mode === 'checkpoint_save') {
    const valid = validateCheckpointSave(requestBody);
    if (!valid.ok) return reply({ ...base, success: false, mode, error: valid.error }, 422);
    const response = await fetch(`${owner.url}/rest/v1/rpc/agent_save_checkpoint`, {
      method: 'POST',
      headers: providerHeaders(owner, auth),
      body: JSON.stringify({
        p_task_id: valid.task_id,
        p_expected_revision: valid.expected_revision,
        p_status: valid.status,
        p_state: valid.state,
      }),
    });
    const data = await readJson(response);
    if (!response.ok) return reply({ ...base, ...persistenceError(data, response.status), mode }, response.status);
    const newRevision = typeof data === 'number' ? data : Number(data);
    const verified = await getCheckpoint(owner, auth, valid.task_id);
    if (!verified.ok || !verified.row || Number((verified.row as Record<string, unknown>).revision) !== newRevision) {
      return reply({ ...base, success: false, mode, error: 'Checkpoint save could not be verified' }, 500);
    }
    return reply({ ...base, mode, checkpoint: verified.row, revision: newRevision, saved: true, state_persisted: true });
  }

  if (mode === 'event_append') {
    const valid = validateActivityAppend(requestBody);
    if (!valid.ok) {
      return reply({ ...base, success: false, mode, error: valid.error, ...('secret_path' in valid ? { secret_path: valid.secret_path } : {}) }, 422);
    }
    const response = await fetch(`${owner.url}/rest/v1/rpc/agent_append_event`, {
      method: 'POST',
      headers: providerHeaders(owner, auth),
      body: JSON.stringify({
        p_task_id: valid.task_id,
        p_event_type: valid.event_type,
        p_step_id: valid.step_id,
        p_payload: valid.payload,
      }),
    });
    const data = await readJson(response);
    if (!response.ok) return reply({ ...base, ...persistenceError(data, response.status), mode }, response.status);
    const eventId = typeof data === 'number' ? data : Number(data);
    if (!Number.isSafeInteger(eventId) || eventId <= 0) {
      return reply({ ...base, success: false, mode, error: 'Activity append returned an invalid event id' }, 500);
    }
    const verified = await getActivityEvent(owner, auth, valid.task_id, eventId);
    if (!verified.ok || !verified.row) {
      return reply({ ...base, success: false, mode, error: 'Activity append could not be verified' }, 500);
    }
    return reply({ ...base, mode, event: verified.row, event_persisted: true }, 201);
  }

  if (mode === 'event_list') {
    const valid = validateActivityList(requestBody);
    if (!valid.ok) return reply({ ...base, success: false, mode, error: valid.error }, 422);
    const cursor = valid.after_event_id === null ? '' : `&event_id=gt.${valid.after_event_id}`;
    const response = await fetch(
      `${owner.url}/rest/v1/agent_task_events?task_id=eq.${encodeURIComponent(valid.task_id)}&select=${encodeURIComponent(EVENT_SELECT)}${cursor}&order=event_id.asc&limit=${valid.limit}`,
      { headers: providerHeaders(owner, auth) },
    );
    const data = await readJson(response);
    if (!response.ok) return reply({ ...base, ...persistenceError(data, response.status), mode }, response.status);
    return reply({ ...base, mode, events: Array.isArray(data) ? data : [], activity_persisted: true });
  }

  return reply(
    {
      ...base,
      success: false,
      error: `mode must be preflight or one of: ${[...CHECKPOINT_MODES, ...ACTIVITY_MODES].join(', ')}`,
    },
    400,
  );
});
