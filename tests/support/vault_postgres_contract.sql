-- Synthetic transactional/ACL prototype only. This is not a migration or real Vault.
-- The fixture may be COMMITted only inside the disposable agent_checkpoint_ci database.
DO $$ BEGIN
  IF current_database() <> 'agent_checkpoint_ci' THEN
    RAISE EXCEPTION 'refusing_non_ephemeral_database';
  END IF;
END $$;

CREATE ROLE secret_test_host_a LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
CREATE ROLE secret_test_host_b LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
CREATE ROLE secret_test_broker NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
CREATE ROLE anon NOLOGIN;
CREATE ROLE authenticated NOLOGIN;
CREATE ROLE service_role NOLOGIN BYPASSRLS;
CREATE ROLE authenticator NOLOGIN;

CREATE SCHEMA auth;
CREATE FUNCTION auth.uid() RETURNS uuid LANGUAGE sql STABLE AS $$
  SELECT nullif(current_setting('request.jwt.claim.sub', true), '')::uuid;
$$;
REVOKE ALL ON FUNCTION auth.uid() FROM PUBLIC;
GRANT USAGE ON SCHEMA auth TO secret_test_broker;
GRANT EXECUTE ON FUNCTION auth.uid() TO secret_test_broker;

CREATE SCHEMA synthetic_vault;
REVOKE ALL ON SCHEMA synthetic_vault FROM PUBLIC;
-- Plaintext is intentional and ONLY suitable for synthetic markers in this fixture.
CREATE TABLE synthetic_vault.secrets (
  id bigint PRIMARY KEY,
  value text NOT NULL CHECK (value LIKE 'SYNTHETIC:%' AND length(value) > length('SYNTHETIC:'))
);
GRANT USAGE ON SCHEMA synthetic_vault TO secret_test_broker;
GRANT SELECT, UPDATE, DELETE ON synthetic_vault.secrets TO secret_test_broker;

CREATE SCHEMA agent_credential_private;
REVOKE ALL ON SCHEMA agent_credential_private FROM PUBLIC;
CREATE TABLE agent_credential_private.bindings (
  binding_key text PRIMARY KEY CHECK (binding_key <> '' AND binding_key = btrim(binding_key)),
  schema_version text NOT NULL CHECK (schema_version = 'credential-refresh-secret-record-v1'),
  provider_id text NOT NULL CHECK (provider_id <> '' AND provider_id = btrim(provider_id)),
  account_id text NOT NULL CHECK (account_id <> '' AND account_id = btrim(account_id)),
  capabilities text[] NOT NULL CHECK (cardinality(capabilities) > 0 AND array_position(capabilities, NULL) IS NULL),
  version bigint NOT NULL CHECK (version >= 0),
  state text NOT NULL CHECK (
    state IN ('ready', 'refreshing', 'blocked_auth', 'blocked_ambiguous', 'revoked')
  ),
  refresh_generation bigint NOT NULL CHECK (refresh_generation >= 0),
  active_attempt_id text,
  last_attempt_id text,
  failure text,
  secret_id bigint UNIQUE REFERENCES synthetic_vault.secrets(id),
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
  binding_key text NOT NULL REFERENCES agent_credential_private.bindings(binding_key),
  PRIMARY KEY (host_login, binding_key)
);
ALTER TABLE agent_credential_private.bindings ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_credential_private.bindings FORCE ROW LEVEL SECURITY;
ALTER TABLE agent_credential_private.host_bindings ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_credential_private.host_bindings FORCE ROW LEVEL SECURITY;
CREATE POLICY own_mapping ON agent_credential_private.host_bindings
  FOR SELECT TO secret_test_broker USING (host_login = session_user);
CREATE POLICY mapped_binding ON agent_credential_private.bindings
  TO secret_test_broker
  USING (EXISTS (
    SELECT 1 FROM agent_credential_private.host_bindings AS m
    WHERE m.host_login = session_user AND m.binding_key = bindings.binding_key
  ))
  WITH CHECK (EXISTS (
    SELECT 1 FROM agent_credential_private.host_bindings AS m
    WHERE m.host_login = session_user AND m.binding_key = bindings.binding_key
  ));
GRANT USAGE ON SCHEMA agent_credential_private TO secret_test_broker;
GRANT SELECT ON agent_credential_private.host_bindings TO secret_test_broker;
GRANT SELECT, UPDATE ON agent_credential_private.bindings TO secret_test_broker;

-- Operator-controlled fault injection, inaccessible to either runtime login.
CREATE TABLE synthetic_vault.test_faults (operation text PRIMARY KEY);
GRANT SELECT ON synthetic_vault.test_faults TO secret_test_broker;
CREATE FUNCTION synthetic_vault.fail_metadata_update() RETURNS trigger
LANGUAGE plpgsql SECURITY INVOKER SET search_path = pg_catalog, pg_temp AS $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM synthetic_vault.test_faults WHERE operation = 'metadata_update'
  ) THEN
    RAISE EXCEPTION 'synthetic_metadata_failure' USING ERRCODE = 'P0001';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER synthetic_metadata_failure
  BEFORE UPDATE ON agent_credential_private.bindings
  FOR EACH ROW EXECUTE FUNCTION synthetic_vault.fail_metadata_update();

CREATE FUNCTION agent_credential_private.read_binding(p_key text)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, pg_temp AS $$
DECLARE result jsonb;
BEGIN
  IF auth.uid() IS NOT NULL OR NOT EXISTS (
    SELECT 1 FROM agent_credential_private.host_bindings
    WHERE host_login = session_user AND binding_key = p_key
  ) THEN
    RAISE EXCEPTION 'credential_binding_denied' USING ERRCODE = '42501';
  END IF;

  -- One statement/snapshot observes the complete metadata row and synthetic secret.
  SELECT jsonb_build_object(
      'schema_version', b.schema_version,
      'provider_id', b.provider_id,
      'account_id', b.account_id,
      'capabilities', to_jsonb(b.capabilities),
      'version', b.version,
      'state', b.state,
      'refresh_secret', s.value,
      'refresh_generation', b.refresh_generation,
      'active_attempt_id', b.active_attempt_id,
      'last_attempt_id', b.last_attempt_id,
      'failure', b.failure
    )
    INTO result
    FROM agent_credential_private.bindings AS b
    LEFT JOIN synthetic_vault.secrets AS s ON s.id = b.secret_id
    WHERE b.binding_key = p_key;

  IF result IS NULL THEN
    RAISE EXCEPTION 'credential_binding_missing' USING ERRCODE = 'P0002';
  END IF;
  RETURN result;
END $$;

CREATE FUNCTION agent_credential_private.cas_binding(
  p_key text,
  p_expected bigint,
  p_replacement jsonb
) RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, pg_temp AS $$
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
  IF auth.uid() IS NOT NULL OR NOT EXISTS (
    SELECT 1 FROM agent_credential_private.host_bindings
    WHERE host_login = session_user AND binding_key = p_key
  ) THEN
    RAISE EXCEPTION 'credential_binding_denied' USING ERRCODE = '42501';
  END IF;

  SELECT * INTO current_row
    FROM agent_credential_private.bindings
    WHERE binding_key = p_key
    FOR UPDATE;

  IF NOT FOUND OR p_expected IS NULL OR p_expected < 0
      OR current_row.version <> p_expected THEN
    RAISE EXCEPTION 'credential_version_conflict' USING ERRCODE = 'P0002';
  END IF;

  -- CI-only hold after the row lock proves a second independent session contends here.
  IF current_row.version = p_expected AND EXISTS (
    SELECT 1 FROM synthetic_vault.test_faults
    WHERE operation = 'hold_initial_cas_lock'
  ) THEN
    PERFORM pg_catalog.pg_sleep(1.0);
  END IF;

  IF current_row.state = 'revoked'
      OR p_expected = 9223372036854775807
      OR p_replacement IS NULL
      OR jsonb_typeof(p_replacement) <> 'object'
      OR NOT p_replacement ?& ARRAY[
        'schema_version', 'provider_id', 'account_id', 'capabilities', 'version',
        'state', 'refresh_secret', 'refresh_generation', 'active_attempt_id',
        'last_attempt_id', 'failure'
      ]
      OR (SELECT count(*) FROM jsonb_object_keys(p_replacement)) <> 11
      OR jsonb_typeof(p_replacement->'schema_version') <> 'string'
      OR jsonb_typeof(p_replacement->'provider_id') <> 'string'
      OR jsonb_typeof(p_replacement->'account_id') <> 'string'
      OR jsonb_typeof(p_replacement->'capabilities') <> 'array'
      OR jsonb_typeof(p_replacement->'version') <> 'number'
      OR jsonb_typeof(p_replacement->'state') <> 'string'
      OR jsonb_typeof(p_replacement->'refresh_generation') <> 'number'
      OR jsonb_typeof(p_replacement->'refresh_secret') NOT IN ('string', 'null')
      OR jsonb_typeof(p_replacement->'active_attempt_id') NOT IN ('string', 'null')
      OR jsonb_typeof(p_replacement->'last_attempt_id') NOT IN ('string', 'null')
      OR jsonb_typeof(p_replacement->'failure') NOT IN ('string', 'null') THEN
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
      OR p_replacement->'capabilities' <> to_jsonb(current_row.capabilities)
      OR replacement_version <> p_expected + 1
      OR replacement_generation < 0
      OR replacement_state NOT IN (
        'ready', 'refreshing', 'blocked_auth', 'blocked_ambiguous', 'revoked'
      )
      OR (
        replacement_state = 'revoked'
        AND jsonb_typeof(p_replacement->'refresh_secret') <> 'null'
      )
      OR (
        replacement_state <> 'revoked'
        AND (
          jsonb_typeof(p_replacement->'refresh_secret') <> 'string'
          OR replacement_secret NOT LIKE 'SYNTHETIC:%'
          OR length(replacement_secret) <= length('SYNTHETIC:')
        )
      )
      OR (
        (replacement_state = 'refreshing')
        <> (jsonb_typeof(p_replacement->'active_attempt_id') = 'string')
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
    DELETE FROM synthetic_vault.secrets WHERE id = current_row.secret_id;
  ELSE
    UPDATE synthetic_vault.secrets
      SET value = replacement_secret
      WHERE id = current_row.secret_id;
    IF NOT FOUND THEN
      RAISE EXCEPTION 'credential_secret_missing' USING ERRCODE = 'P0002';
    END IF;
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
END $$;

ALTER FUNCTION agent_credential_private.read_binding(text) OWNER TO secret_test_broker;
ALTER FUNCTION agent_credential_private.cas_binding(text,bigint,jsonb) OWNER TO secret_test_broker;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA agent_credential_private FROM PUBLIC;
GRANT USAGE ON SCHEMA agent_credential_private TO secret_test_host_a, secret_test_host_b;
GRANT EXECUTE ON FUNCTION agent_credential_private.read_binding(text),
  agent_credential_private.cas_binding(text,bigint,jsonb)
  TO secret_test_host_a, secret_test_host_b;

INSERT INTO synthetic_vault.secrets VALUES
  (1, 'SYNTHETIC:a0'),
  (2, 'SYNTHETIC:b0');
INSERT INTO agent_credential_private.bindings (
  binding_key, schema_version, provider_id, account_id, capabilities,
  version, state, refresh_generation, active_attempt_id, last_attempt_id,
  failure, secret_id
) VALUES
  (
    'binding-a', 'credential-refresh-secret-record-v1', 'provider-a', 'account-a',
    ARRAY['read:one','write:one'], 0, 'ready', 0, NULL, NULL, NULL, 1
  ),
  (
    'binding-b', 'credential-refresh-secret-record-v1', 'provider-b', 'account-b',
    ARRAY['read:two'], 0, 'ready', 0, NULL, NULL, NULL, 2
  );
INSERT INTO agent_credential_private.host_bindings VALUES
  ('secret_test_host_a', 'binding-a'),
  ('secret_test_host_b', 'binding-b');

CREATE FUNCTION pg_temp.assert_true(value boolean, label text)
RETURNS void LANGUAGE plpgsql SECURITY INVOKER AS $$
BEGIN
  IF value IS DISTINCT FROM true THEN
    RAISE EXCEPTION 'assertion failed: %', label;
  END IF;
END $$;

CREATE FUNCTION pg_temp.expect_error(statement text, expected text)
RETURNS void LANGUAGE plpgsql SECURITY INVOKER AS $$
BEGIN
  BEGIN
    EXECUTE statement;
  EXCEPTION WHEN OTHERS THEN
    IF sqlstate = expected THEN
      RETURN;
    END IF;
    RAISE EXCEPTION 'unexpected SQLSTATE: %', sqlstate;
  END;
  RAISE EXCEPTION 'expected failure did not occur';
END $$;

CREATE FUNCTION pg_temp.record_a(
  p_version bigint,
  p_state text,
  p_secret text,
  p_generation bigint,
  p_active text,
  p_last text,
  p_failure text
) RETURNS jsonb LANGUAGE sql SECURITY INVOKER AS $$
  SELECT jsonb_build_object(
    'schema_version', 'credential-refresh-secret-record-v1',
    'provider_id', 'provider-a',
    'account_id', 'account-a',
    'capabilities', to_jsonb(ARRAY['read:one','write:one']::text[]),
    'version', p_version,
    'state', p_state,
    'refresh_secret', p_secret,
    'refresh_generation', p_generation,
    'active_attempt_id', p_active,
    'last_attempt_id', p_last,
    'failure', p_failure
  );
$$;
