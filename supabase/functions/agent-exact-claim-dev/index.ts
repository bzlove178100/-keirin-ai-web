import 'jsr:@supabase/functions-js/edge-runtime.d.ts';
import {
  EXACT_CLAIM_MODE,
  EXACT_CLAIM_SAFETY,
  EXACT_CLAIM_SERVICE,
  EXACT_CLAIM_VERSION,
  validateExactClaimRequest,
} from './contract.ts';

const ALLOWED_ORIGIN = 'https://bzlove178100.github.io';
const CHECKPOINT_SELECT = [
  'task_id',
  'status',
  'idempotency_key',
  'spec',
  'state',
  'revision',
  'spec_fingerprint',
  'not_before',
  'attempt_count',
  'max_attempts',
  'lease_owner',
  'lease_generation',
  'lease_expires_at',
  'created_at',
  'updated_at',
].join(',');

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

function providerHeaders(owner: OwnerContext, authHeader: string) {
  return {
    apikey: owner.key,
    Authorization: authHeader,
    Accept: 'application/json',
    'Content-Type': 'application/json',
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

async function queueHealth(owner: OwnerContext, authHeader: string) {
  const response = await fetch(
    `${owner.url}/rest/v1/agent_tasks?select=task_id,lease_generation,lease_expires_at&limit=0`,
    { headers: providerHeaders(owner, authHeader) },
  );
  return response.ok;
}

async function getTask(owner: OwnerContext, authHeader: string, taskId: string) {
  const response = await fetch(
    `${owner.url}/rest/v1/agent_tasks?task_id=eq.${encodeURIComponent(taskId)}&select=${encodeURIComponent(CHECKPOINT_SELECT)}&limit=1`,
    { headers: providerHeaders(owner, authHeader) },
  );
  const data = await readJson(response);
  if (!response.ok) return { ok: false as const, status: response.status, data };
  const rows = Array.isArray(data) ? data : [];
  return { ok: true as const, row: rows.length === 1 ? rows[0] as Record<string, unknown> : null };
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === 'object' && !Array.isArray(value)
    ? value as Record<string, unknown>
    : null;
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

  const queueVerified = await queueHealth(owner, auth);
  const base = {
    success: true,
    service: EXACT_CLAIM_SERVICE,
    service_version: EXACT_CLAIM_VERSION,
    authenticated: true,
    owner: true,
    role: owner.role,
    plan: owner.plan,
    mode: EXACT_CLAIM_MODE,
    safety: EXACT_CLAIM_SAFETY,
    queue_coordination_verified: queueVerified,
    executed: false,
    message: 'Owner-only exact trusted run-instance queue claim. No task/provider execution is performed by this function.',
  };

  if (req.method === 'GET') return reply(base);
  if (!queueVerified) return reply({ ...base, success: false, error: 'Agent queue coordination storage is unavailable' }, 503);

  let body: unknown;
  try {
    body = await req.json();
  } catch (_) {
    return reply({ ...base, success: false, error: 'Invalid JSON body' }, 400);
  }
  const valid = validateExactClaimRequest(body);
  if (!valid.ok) return reply({ ...base, success: false, error: valid.error }, 422);

  const response = await fetch(`${owner.url}/rest/v1/rpc/agent_claim_task`, {
    method: 'POST',
    headers: providerHeaders(owner, auth),
    body: JSON.stringify({
      p_task_id: valid.task_id,
      p_worker_id: valid.worker_id,
      p_lease_seconds: valid.lease_seconds,
    }),
  });
  const data = await readJson(response);
  if (!response.ok) return reply({ ...base, ...persistenceError(data, response.status) }, response.status);
  if (data === null) return reply({ ...base, claimed: false, lease: null });

  const raw = asRecord(data);
  if (!raw || raw.task_id !== valid.task_id) {
    return reply({ ...base, success: false, error: 'Exact claim returned unexpected task identity' }, 500);
  }
  if (raw.status !== 'running' || raw.lease_owner !== valid.worker_id) {
    return reply({ ...base, success: false, error: 'Exact claim returned invalid lease identity' }, 500);
  }

  const verified = await getTask(owner, auth, valid.task_id);
  if (!verified.ok || !verified.row) {
    return reply({ ...base, success: false, error: 'Exact claim could not be read back' }, 500);
  }
  const row = verified.row;
  if (
    row.task_id !== valid.task_id ||
    row.status !== 'running' ||
    row.lease_owner !== valid.worker_id ||
    Number(row.revision) !== Number(raw.revision) ||
    Number(row.lease_generation) !== Number(raw.lease_generation)
  ) {
    return reply({ ...base, success: false, error: 'Exact claim read-back mismatch' }, 500);
  }

  return reply({ ...base, claimed: true, lease: row, queue_state_persisted: true }, 201);
});
