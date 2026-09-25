import 'jsr:@supabase/functions-js/edge-runtime.d.ts';
import {
  AGENT_RUNTIME_SERVICE,
  AGENT_RUNTIME_VERSION,
  RUNTIME_BINDING_SCHEMA_VERSION,
  RUNTIME_CAPABILITIES,
  SAFETY_STATE,
  capabilityDiagnostics,
  preflightTask,
} from './contract.ts';

const ALLOWED_ORIGIN = 'https://bzlove178100.github.io';

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

async function verifyOwner(authHeader: string) {
  const url = Deno.env.get('SUPABASE_URL') ?? '';
  let key = '';
  try {
    const raw = Deno.env.get('SUPABASE_PUBLISHABLE_KEYS');
    if (raw) key = JSON.parse(raw).default ?? '';
  } catch (_) {
    // Fall back to legacy anon key below.
  }
  if (!key) key = Deno.env.get('SUPABASE_ANON_KEY') ?? '';
  if (!url || !key) return { ok: false as const, status: 500, error: 'Server configuration error' };

  const userRes = await fetch(`${url}/auth/v1/user`, {
    headers: { apikey: key, Authorization: authHeader },
  });
  if (!userRes.ok) return { ok: false as const, status: 401, error: 'Invalid or expired session' };
  const user = await userRes.json();
  if (!user?.id) return { ok: false as const, status: 401, error: 'User could not be verified' };

  const profileRes = await fetch(
    `${url}/rest/v1/user_profiles?user_id=eq.${encodeURIComponent(user.id)}&select=role,plan`,
    { headers: { apikey: key, Authorization: authHeader, Accept: 'application/json' } },
  );
  if (!profileRes.ok) return { ok: false as const, status: 403, error: 'Profile lookup failed' };
  const rows = await profileRes.json();
  const profile = Array.isArray(rows) && rows.length === 1 ? rows[0] : null;
  if (profile?.role !== 'owner' || profile?.plan !== 'owner') {
    return { ok: false as const, status: 403, error: 'Owner access required' };
  }
  return { ok: true as const, role: profile.role, plan: profile.plan };
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
    capabilities: RUNTIME_CAPABILITIES,
    diagnostics: {
      runtime_mode: 'owner_preflight_only',
      execution_enabled: false,
      persistence_enabled: false,
      capability_status: diagnostics,
    },
    message:
      'Owner-only hosted runtime shell. Current version provides status/diagnostics and preflight only: no task execution, persistence, provider writes, automatic keirin race-data fetching, or report delivery.',
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
  if (requestBody.mode !== 'preflight') {
    return reply(
      {
        success: false,
        service: AGENT_RUNTIME_SERVICE,
        service_version: AGENT_RUNTIME_VERSION,
        error: 'mode must be preflight; task execution is disabled',
        safety: SAFETY_STATE,
        diagnostics: base.diagnostics,
      },
      400,
    );
  }

  const result = preflightTask(requestBody.task, requestBody.allowed_access ?? ['read']);
  if (!result.ok) {
    return reply(
      {
        success: false,
        service: AGENT_RUNTIME_SERVICE,
        service_version: AGENT_RUNTIME_VERSION,
        mode: 'preflight',
        error: result.error,
        ...('secret_path' in result ? { secret_path: result.secret_path } : {}),
        safety: SAFETY_STATE,
        diagnostics: base.diagnostics,
      },
      422,
    );
  }

  return reply({
    ...base,
    mode: 'preflight',
    preflight: result,
    executed: false,
    saved: false,
    state_persisted: false,
  });
});
