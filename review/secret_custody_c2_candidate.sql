-- REVIEW-ONLY C2 CANDIDATE FOR THE DEDICATED SECRET-CUSTODY PROJECT.
-- DO NOT APPLY WITHOUT A NEW, EXPLICIT C2 LIVE-APPLY APPROVAL.
-- This file is intentionally outside supabase/migrations.
--
-- IMPORTANT: this database transaction cannot prove the management-plane gates.
-- Before any live apply, independently verify on the actual custody project:
--   * Data API disabled;
--   * custody-project service/secret key not distributed to runtime;
--   * Postgres SSL enforcement enabled;
--   * database/pooler ingress restricted to the approved host CIDR(s).
--
-- No password, secret value, binding row, provider credential or task data appears here.
-- The dedicated project intentionally retains Supabase platform service_role Vault access;
-- isolation comes from the separate project boundary and non-distribution of its service key.

BEGIN;
SET LOCAL lock_timeout = '3s';
SET LOCAL statement_timeout = '30s';
SET LOCAL idle_in_transaction_session_timeout = '30s';

DO $c2_preflight$
DECLARE
  v_vault_version text;
  v_update_owner name;
  v_update_security_definer boolean;
  v_create_owner name;
  v_create_security_definer boolean;
  v_secret_id_type text;
  v_decrypted_id_type text;
  v_service_role_login boolean;
  v_service_role_bypassrls boolean;
BEGIN
  IF pg_catalog.current_setting('server_version_num')::integer <> 170006 THEN
    RAISE EXCEPTION 'c2_preflight_server_version_mismatch' USING ERRCODE = '55000';
  END IF;

  IF current_user <> 'postgres'::name THEN
    RAISE EXCEPTION 'c2_preflight_executor_mismatch' USING ERRCODE = '42501';
  END IF;

  SELECT e.extversion INTO v_vault_version
  FROM pg_catalog.pg_extension AS e
  WHERE e.extname = 'supabase_vault';

  IF v_vault_version IS DISTINCT FROM '0.3.1' THEN
    RAISE EXCEPTION 'c2_preflight_vault_version_mismatch' USING ERRCODE = '55000';
  END IF;

  IF pg_catalog.to_regrole('agent_secret_host') IS NOT NULL
      OR pg_catalog.to_regrole('agent_secret_broker') IS NOT NULL
      OR pg_catalog.to_regnamespace('agent_credential_private') IS NOT NULL THEN
    RAISE EXCEPTION 'c2_preflight_name_conflict' USING ERRCODE = '55000';
  END IF;

  IF pg_catalog.to_regprocedure('auth.uid()') IS NULL THEN
    RAISE EXCEPTION 'c2_preflight_auth_uid_missing' USING ERRCODE = '55000';
  END IF;

  IF pg_catalog.to_regprocedure('vault.create_secret(text,text,text,uuid)') IS NULL
      OR pg_catalog.to_regprocedure('vault.update_secret(uuid,text,text,text,uuid)') IS NULL THEN
    RAISE EXCEPTION 'c2_preflight_vault_signature_mismatch' USING ERRCODE = '55000';
  END IF;

  SELECT pg_catalog.pg_get_userbyid(p.proowner), p.prosecdef
    INTO v_create_owner, v_create_security_definer
  FROM pg_catalog.pg_proc AS p
  WHERE p.oid = pg_catalog.to_regprocedure('vault.create_secret(text,text,text,uuid)');

  SELECT pg_catalog.pg_get_userbyid(p.proowner), p.prosecdef
    INTO v_update_owner, v_update_security_definer
  FROM pg_catalog.pg_proc AS p
  WHERE p.oid = pg_catalog.to_regprocedure('vault.update_secret(uuid,text,text,text,uuid)');

  IF v_create_owner IS DISTINCT FROM 'supabase_admin'::name
      OR v_update_owner IS DISTINCT FROM 'supabase_admin'::name
      OR v_create_security_definer IS DISTINCT FROM true
      OR v_update_security_definer IS DISTINCT FROM true THEN
    RAISE EXCEPTION 'c2_preflight_vault_owner_or_security_mismatch'
      USING ERRCODE = '55000';
  END IF;

  SELECT pg_catalog.format_type(a.atttypid, a.atttypmod)
    INTO v_secret_id_type
  FROM pg_catalog.pg_attribute AS a
  JOIN pg_catalog.pg_class AS c ON c.oid = a.attrelid
  JOIN pg_catalog.pg_namespace AS n ON n.oid = c.relnamespace
  WHERE n.nspname = 'vault'
    AND c.relname = 'secrets'
    AND a.attname = 'id'
    AND a.attnum > 0
    AND NOT a.attisdropped;

  SELECT pg_catalog.format_type(a.atttypid, a.atttypmod)
    INTO v_decrypted_id_type
  FROM pg_catalog.pg_attribute AS a
  JOIN pg_catalog.pg_class AS c ON c.oid = a.attrelid
  JOIN pg_catalog.pg_namespace AS n ON n.oid = c.relnamespace
  WHERE n.nspname = 'vault'
    AND c.relname = 'decrypted_secrets'
    AND a.attname = 'id'
    AND a.attnum > 0
    AND NOT a.attisdropped;

  IF v_secret_id_type IS DISTINCT FROM 'uuid'
      OR v_decrypted_id_type IS DISTINCT FROM 'uuid' THEN
    RAISE EXCEPTION 'c2_preflight_vault_id_type_mismatch' USING ERRCODE = '55000';
  END IF;

  SELECT r.rolcanlogin, r.rolbypassrls
    INTO v_service_role_login, v_service_role_bypassrls
  FROM pg_catalog.pg_roles AS r
  WHERE r.rolname = 'service_role';

  IF NOT FOUND
      OR v_service_role_login IS DISTINCT FROM false
      OR v_service_role_bypassrls IS DISTINCT FROM true THEN
    RAISE EXCEPTION 'c2_preflight_platform_role_shape_mismatch' USING ERRCODE = '55000';
  END IF;

  -- The dedicated-project design intentionally does not revoke or require absence of
  -- platform-managed service_role Vault grants. Those grants are outside the runtime path.
END
$c2_preflight$;

-- Roles are intentionally created without a usable runtime password.
CREATE ROLE agent_secret_broker
  NOLOGIN
  NOSUPERUSER
  NOCREATEDB
  NOCREATEROLE
  NOREPLICATION
  NOBYPASSRLS;

CREATE ROLE agent_secret_host
  LOGIN
  PASSWORD NULL
  NOSUPERUSER
  NOCREATEDB
  NOCREATEROLE
  NOREPLICATION
  NOBYPASSRLS;

CREATE SCHEMA agent_credential_private AUTHORIZATION postgres;
REVOKE ALL ON SCHEMA agent_credential_private
  FROM PUBLIC, anon, authenticated, authenticator, service_role,
       agent_secret_host, agent_secret_broker;
GRANT USAGE ON SCHEMA agent_credential_private TO agent_secret_broker;

ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA agent_credential_private
  REVOKE ALL ON TABLES FROM PUBLIC, anon, authenticated, authenticator, service_role;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA agent_credential_private
  REVOKE ALL ON FUNCTIONS FROM PUBLIC, anon, authenticated, authenticator, service_role;

CREATE TABLE agent_credential_private.bindings (
  binding_key text PRIMARY KEY
    CHECK (binding_key <> '' AND binding_key = pg_catalog.btrim(binding_key)),
  schema_version text NOT NULL
    CHECK (schema_version = 'credential-refresh-secret-record-v1'),
  provider_id text NOT NULL
    CHECK (provider_id <> '' AND provider_id = pg_catalog.btrim(provider_id)),
  account_id text NOT NULL
    CHECK (account_id <> '' AND account_id = pg_catalog.btrim(account_id)),
  capabilities text[] NOT NULL
    CHECK (
      pg_catalog.cardinality(capabilities) > 0
      AND pg_catalog.array_position(capabilities, NULL) IS NULL
    ),
  version bigint NOT NULL CHECK (version >= 0),
  state text NOT NULL CHECK (
    state IN ('ready', 'refreshing', 'blocked_auth', 'blocked_ambiguous', 'revoked')
  ),
  refresh_generation bigint NOT NULL CHECK (refresh_generation >= 0),
  active_attempt_id text,
  last_attempt_id text,
  failure text,
  secret_id uuid UNIQUE,
  CHECK (
    active_attempt_id IS NULL
    OR active_attempt_id ~ '^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$'
  ),
  CHECK (
    last_attempt_id IS NULL
    OR last_attempt_id ~ '^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$'
  ),
  CHECK (
    failure IS NULL OR failure IN (
      'refresh_rejected',
      'refresh_outcome_ambiguous',
      'refresh_response_invalid_or_incomplete',
      'secret_store_commit_ambiguous',
      'credential_source_revoked'
    )
  ),
  CHECK ((state = 'revoked') = (secret_id IS NULL)),
  CHECK ((state = 'refreshing') = (active_attempt_id IS NOT NULL))
);

CREATE TABLE agent_credential_private.host_bindings (
  host_login name NOT NULL,
  binding_key text NOT NULL
    REFERENCES agent_credential_private.bindings(binding_key),
  PRIMARY KEY (host_login, binding_key),
  CHECK (host_login = 'agent_secret_host'::name)
);

ALTER TABLE agent_credential_private.bindings ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_credential_private.bindings FORCE ROW LEVEL SECURITY;
ALTER TABLE agent_credential_private.host_bindings ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_credential_private.host_bindings FORCE ROW LEVEL SECURITY;

CREATE POLICY broker_mapping_select
  ON agent_credential_private.host_bindings
  FOR SELECT TO agent_secret_broker
  USING (host_login = session_user);

CREATE POLICY broker_binding_access
  ON agent_credential_private.bindings
  TO agent_secret_broker
  USING (
    EXISTS (
      SELECT 1
      FROM agent_credential_private.host_bindings AS m
      WHERE m.host_login = session_user
        AND m.binding_key = bindings.binding_key
    )
  )
  WITH CHECK (
    EXISTS (
      SELECT 1
      FROM agent_credential_private.host_bindings AS m
      WHERE m.host_login = session_user
        AND m.binding_key = bindings.binding_key
    )
  );

REVOKE ALL ON ALL TABLES IN SCHEMA agent_credential_private
  FROM PUBLIC, anon, authenticated, authenticator, service_role, agent_secret_host;
GRANT SELECT ON agent_credential_private.host_bindings TO agent_secret_broker;
GRANT SELECT, UPDATE ON agent_credential_private.bindings TO agent_secret_broker;

GRANT USAGE ON SCHEMA auth TO agent_secret_broker;
GRANT EXECUTE ON FUNCTION auth.uid() TO agent_secret_broker;
GRANT USAGE ON SCHEMA vault TO agent_secret_broker;
GRANT SELECT ON vault.decrypted_secrets TO agent_secret_broker;
GRANT DELETE ON vault.secrets TO agent_secret_broker;
GRANT EXECUTE ON FUNCTION vault.update_secret(uuid,text,text,text,uuid)
  TO agent_secret_broker;

CREATE FUNCTION agent_credential_private.read_binding(p_key text)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $read_binding$
DECLARE
  result jsonb;
BEGIN
  IF session_user <> 'agent_secret_host'::name
      OR auth.uid() IS NOT NULL
      OR NOT EXISTS (
        SELECT 1
        FROM agent_credential_private.host_bindings AS m
        WHERE m.host_login = session_user
          AND m.binding_key = p_key
      ) THEN
    RAISE EXCEPTION 'credential_binding_denied' USING ERRCODE = '42501';
  END IF;

  SELECT pg_catalog.jsonb_build_object(
      'schema_version', b.schema_version,
      'provider_id', b.provider_id,
      'account_id', b.account_id,
      'capabilities', pg_catalog.to_jsonb(b.capabilities),
      'version', b.version,
      'state', b.state,
      'refresh_secret', s.decrypted_secret,
      'refresh_generation', b.refresh_generation,
      'active_attempt_id', b.active_attempt_id,
      'last_attempt_id', b.last_attempt_id,
      'failure', b.failure
    )
    INTO result
    FROM agent_credential_private.bindings AS b
    LEFT JOIN vault.decrypted_secrets AS s ON s.id = b.secret_id
    WHERE b.binding_key = p_key;

  IF result IS NULL THEN
    RAISE EXCEPTION 'credential_binding_missing' USING ERRCODE = 'P0002';
  END IF;

  IF result->>'state' <> 'revoked'
      AND pg_catalog.jsonb_typeof(result->'refresh_secret') <> 'string' THEN
    RAISE EXCEPTION 'credential_secret_missing' USING ERRCODE = 'P0002';
  END IF;

  RETURN result;
END
$read_binding$;

CREATE FUNCTION agent_credential_private.cas_binding(
  p_key text,
  p_expected bigint,
  p_replacement jsonb
) RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $cas_binding$
DECLARE
  current_row agent_credential_private.bindings%ROWTYPE;
  replacement_version bigint;
  replacement_generation bigint;
  replacement_state text;
  replacement_secret text;
  replacement_active_attempt text;
  replacement_last_attempt text;
  replacement_failure text;
BEGIN
  IF session_user <> 'agent_secret_host'::name
      OR auth.uid() IS NOT NULL
      OR NOT EXISTS (
        SELECT 1
        FROM agent_credential_private.host_bindings AS m
        WHERE m.host_login = session_user
          AND m.binding_key = p_key
      ) THEN
    RAISE EXCEPTION 'credential_binding_denied' USING ERRCODE = '42501';
  END IF;

  SELECT * INTO current_row
  FROM agent_credential_private.bindings
  WHERE binding_key = p_key
  FOR UPDATE;

  IF NOT FOUND
      OR p_expected IS NULL
      OR p_expected < 0
      OR current_row.version <> p_expected THEN
    RAISE EXCEPTION 'credential_version_conflict' USING ERRCODE = 'P0002';
  END IF;

  IF current_row.state = 'revoked' OR p_expected = 9223372036854775807 THEN
    RAISE EXCEPTION 'credential_replacement_invalid' USING ERRCODE = '22023';
  END IF;

  IF p_replacement IS NULL
      OR pg_catalog.jsonb_typeof(p_replacement) <> 'object'
      OR NOT p_replacement ?& ARRAY[
        'schema_version', 'provider_id', 'account_id', 'capabilities', 'version',
        'state', 'refresh_secret', 'refresh_generation', 'active_attempt_id',
        'last_attempt_id', 'failure'
      ]
      OR (SELECT count(*) FROM pg_catalog.jsonb_object_keys(p_replacement)) <> 11
      OR pg_catalog.jsonb_typeof(p_replacement->'schema_version') <> 'string'
      OR pg_catalog.jsonb_typeof(p_replacement->'provider_id') <> 'string'
      OR pg_catalog.jsonb_typeof(p_replacement->'account_id') <> 'string'
      OR pg_catalog.jsonb_typeof(p_replacement->'capabilities') <> 'array'
      OR pg_catalog.jsonb_typeof(p_replacement->'version') <> 'number'
      OR pg_catalog.jsonb_typeof(p_replacement->'state') <> 'string'
      OR pg_catalog.jsonb_typeof(p_replacement->'refresh_generation') <> 'number'
      OR pg_catalog.jsonb_typeof(p_replacement->'refresh_secret') NOT IN ('string', 'null')
      OR pg_catalog.jsonb_typeof(p_replacement->'active_attempt_id') NOT IN ('string', 'null')
      OR pg_catalog.jsonb_typeof(p_replacement->'last_attempt_id') NOT IN ('string', 'null')
      OR pg_catalog.jsonb_typeof(p_replacement->'failure') NOT IN ('string', 'null') THEN
    RAISE EXCEPTION 'credential_replacement_invalid' USING ERRCODE = '22023';
  END IF;

  BEGIN
    replacement_version := (p_replacement->>'version')::bigint;
    replacement_generation := (p_replacement->>'refresh_generation')::bigint;
  EXCEPTION
    WHEN invalid_text_representation OR numeric_value_out_of_range THEN
      RAISE EXCEPTION 'credential_replacement_invalid' USING ERRCODE = '22023';
  END;

  replacement_state := p_replacement->>'state';
  replacement_secret := p_replacement->>'refresh_secret';
  replacement_active_attempt := p_replacement->>'active_attempt_id';
  replacement_last_attempt := p_replacement->>'last_attempt_id';
  replacement_failure := p_replacement->>'failure';

  IF p_replacement->>'schema_version' <> current_row.schema_version
      OR p_replacement->>'provider_id' <> current_row.provider_id
      OR p_replacement->>'account_id' <> current_row.account_id
      OR p_replacement->'capabilities' <> pg_catalog.to_jsonb(current_row.capabilities)
      OR replacement_version <> p_expected + 1
      OR replacement_generation < 0
      OR replacement_state NOT IN (
        'ready', 'refreshing', 'blocked_auth', 'blocked_ambiguous', 'revoked'
      )
      OR (
        replacement_state = 'revoked'
        AND pg_catalog.jsonb_typeof(p_replacement->'refresh_secret') <> 'null'
      )
      OR (
        replacement_state <> 'revoked'
        AND (
          pg_catalog.jsonb_typeof(p_replacement->'refresh_secret') <> 'string'
          OR replacement_secret IS NULL
          OR replacement_secret = ''
        )
      )
      OR (
        (replacement_state = 'refreshing')
        <> (pg_catalog.jsonb_typeof(p_replacement->'active_attempt_id') = 'string')
      )
      OR (
        replacement_active_attempt IS NOT NULL
        AND replacement_active_attempt !~ '^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$'
      )
      OR (
        replacement_last_attempt IS NOT NULL
        AND replacement_last_attempt !~ '^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$'
      )
      OR (
        replacement_failure IS NOT NULL
        AND replacement_failure NOT IN (
          'refresh_rejected',
          'refresh_outcome_ambiguous',
          'refresh_response_invalid_or_incomplete',
          'secret_store_commit_ambiguous',
          'credential_source_revoked'
        )
      ) THEN
    RAISE EXCEPTION 'credential_replacement_invalid' USING ERRCODE = '22023';
  END IF;

  IF current_row.secret_id IS NULL THEN
    RAISE EXCEPTION 'credential_secret_missing' USING ERRCODE = 'P0002';
  END IF;

  IF NOT EXISTS (
    SELECT 1
    FROM vault.decrypted_secrets AS s
    WHERE s.id = current_row.secret_id
  ) THEN
    RAISE EXCEPTION 'credential_secret_missing' USING ERRCODE = 'P0002';
  END IF;

  IF replacement_state = 'revoked' THEN
    UPDATE agent_credential_private.bindings
    SET version = replacement_version,
        state = replacement_state,
        refresh_generation = replacement_generation,
        active_attempt_id = replacement_active_attempt,
        last_attempt_id = replacement_last_attempt,
        failure = replacement_failure,
        secret_id = NULL
    WHERE binding_key = p_key;

    DELETE FROM vault.secrets
    WHERE id = current_row.secret_id;

    IF NOT FOUND THEN
      RAISE EXCEPTION 'credential_secret_missing' USING ERRCODE = 'P0002';
    END IF;
  ELSE
    PERFORM vault.update_secret(
      current_row.secret_id,
      replacement_secret,
      NULL,
      NULL,
      NULL
    );

    UPDATE agent_credential_private.bindings
    SET version = replacement_version,
        state = replacement_state,
        refresh_generation = replacement_generation,
        active_attempt_id = replacement_active_attempt,
        last_attempt_id = replacement_last_attempt,
        failure = replacement_failure
    WHERE binding_key = p_key;
  END IF;

  RETURN agent_credential_private.read_binding(p_key);
END
$cas_binding$;

ALTER FUNCTION agent_credential_private.read_binding(text)
  OWNER TO agent_secret_broker;
ALTER FUNCTION agent_credential_private.cas_binding(text,bigint,jsonb)
  OWNER TO agent_secret_broker;

REVOKE ALL ON FUNCTION agent_credential_private.read_binding(text)
  FROM PUBLIC, anon, authenticated, authenticator, service_role, agent_secret_broker;
REVOKE ALL ON FUNCTION agent_credential_private.cas_binding(text,bigint,jsonb)
  FROM PUBLIC, anon, authenticated, authenticator, service_role, agent_secret_broker;

GRANT USAGE ON SCHEMA agent_credential_private TO agent_secret_host;
GRANT EXECUTE ON FUNCTION agent_credential_private.read_binding(text)
  TO agent_secret_host;
GRANT EXECUTE ON FUNCTION agent_credential_private.cas_binding(text,bigint,jsonb)
  TO agent_secret_host;

REVOKE ALL ON SCHEMA agent_credential_private
  FROM PUBLIC, anon, authenticated, authenticator, service_role;
REVOKE ALL ON ALL TABLES IN SCHEMA agent_credential_private
  FROM PUBLIC, anon, authenticated, authenticator, service_role, agent_secret_host;

COMMIT;
