-- Synthetic transactional/ACL prototype only. This is not a migration or real Vault.
-- The caller wraps all setup and cases in one transaction followed by ROLLBACK.
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
  value text NOT NULL CHECK (value LIKE 'SYNTHETIC:%')
);
GRANT USAGE ON SCHEMA synthetic_vault TO secret_test_broker;
GRANT SELECT, UPDATE, DELETE ON synthetic_vault.secrets TO secret_test_broker;

CREATE SCHEMA agent_credential_private;
REVOKE ALL ON SCHEMA agent_credential_private FROM PUBLIC;
CREATE TABLE agent_credential_private.bindings (
  binding_key text PRIMARY KEY,
  version bigint NOT NULL CHECK (version >= 0),
  state text NOT NULL CHECK (state IN ('ready', 'refreshing', 'blocked_ambiguous', 'revoked')),
  secret_id bigint UNIQUE REFERENCES synthetic_vault.secrets(id),
  CHECK ((state = 'revoked') = (secret_id IS NULL))
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
  IF EXISTS (SELECT 1 FROM synthetic_vault.test_faults WHERE operation='metadata_update') THEN
    RAISE EXCEPTION 'synthetic_metadata_failure' USING ERRCODE = 'P0001';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER synthetic_metadata_failure BEFORE UPDATE ON agent_credential_private.bindings
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
  -- One snapshot observes both metadata and the synthetic secret.
  SELECT jsonb_build_object('version', b.version, 'state', b.state, 'refresh_secret', s.value)
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
  p_key text, p_expected bigint, p_state text, p_secret text
) RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, pg_temp AS $$
DECLARE current_row agent_credential_private.bindings%ROWTYPE;
BEGIN
  IF auth.uid() IS NOT NULL OR NOT EXISTS (
    SELECT 1 FROM agent_credential_private.host_bindings
    WHERE host_login = session_user AND binding_key = p_key
  ) THEN
    RAISE EXCEPTION 'credential_binding_denied' USING ERRCODE = '42501';
  END IF;
  SELECT * INTO current_row FROM agent_credential_private.bindings
    WHERE binding_key = p_key FOR UPDATE;
  IF NOT FOUND OR p_expected IS NULL OR current_row.version <> p_expected THEN
    RAISE EXCEPTION 'credential_version_conflict' USING ERRCODE = 'P0002';
  END IF;
  IF current_row.state = 'revoked' OR p_expected = 9223372036854775807
      OR p_state IS NULL OR p_state NOT IN ('ready', 'refreshing', 'blocked_ambiguous', 'revoked')
      OR (p_state = 'revoked' AND p_secret IS NOT NULL)
      OR (p_state <> 'revoked' AND (p_secret IS NULL OR p_secret NOT LIKE 'SYNTHETIC:%')) THEN
    RAISE EXCEPTION 'credential_replacement_invalid' USING ERRCODE = '22023';
  END IF;

  IF p_state = 'revoked' THEN
    UPDATE agent_credential_private.bindings
      SET version = version + 1, state = p_state, secret_id = NULL
      WHERE binding_key = p_key;
    DELETE FROM synthetic_vault.secrets WHERE id = current_row.secret_id;
  ELSE
    UPDATE synthetic_vault.secrets SET value = p_secret WHERE id = current_row.secret_id;
    IF NOT FOUND THEN
      RAISE EXCEPTION 'credential_secret_missing' USING ERRCODE = 'P0002';
    END IF;
    UPDATE agent_credential_private.bindings
      SET version = version + 1, state = p_state WHERE binding_key = p_key;
  END IF;
  RETURN agent_credential_private.read_binding(p_key);
END $$;

ALTER FUNCTION agent_credential_private.read_binding(text) OWNER TO secret_test_broker;
ALTER FUNCTION agent_credential_private.cas_binding(text,bigint,text,text) OWNER TO secret_test_broker;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA agent_credential_private FROM PUBLIC;
GRANT USAGE ON SCHEMA agent_credential_private TO secret_test_host_a, secret_test_host_b;
GRANT EXECUTE ON FUNCTION agent_credential_private.read_binding(text),
  agent_credential_private.cas_binding(text,bigint,text,text)
  TO secret_test_host_a, secret_test_host_b;

INSERT INTO synthetic_vault.secrets VALUES (1, 'SYNTHETIC:a0'), (2, 'SYNTHETIC:b0');
INSERT INTO agent_credential_private.bindings VALUES
  ('binding-a', 0, 'ready', 1), ('binding-b', 0, 'ready', 2);
INSERT INTO agent_credential_private.host_bindings VALUES
  ('secret_test_host_a', 'binding-a'), ('secret_test_host_b', 'binding-b');

CREATE FUNCTION pg_temp.assert_true(value boolean, label text)
RETURNS void LANGUAGE plpgsql SECURITY INVOKER AS $$
BEGIN
  IF value IS DISTINCT FROM true THEN RAISE EXCEPTION 'assertion failed: %', label; END IF;
END $$;
CREATE FUNCTION pg_temp.expect_error(statement text, expected text)
RETURNS void LANGUAGE plpgsql SECURITY INVOKER AS $$
BEGIN
  BEGIN
    EXECUTE statement;
  EXCEPTION WHEN OTHERS THEN
    IF sqlstate = expected THEN RETURN; END IF;
    RAISE EXCEPTION 'unexpected SQLSTATE: %', sqlstate;
  END;
  RAISE EXCEPTION 'expected failure did not occur';
END $$;
