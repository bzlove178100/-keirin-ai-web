-- REVIEW-ONLY STRUCTURAL ROLLBACK CANDIDATE.
-- Valid only before any real credential has ever been provisioned.
-- Do not use CASCADE. Do not use this as provider revocation.

BEGIN;
SET LOCAL lock_timeout = '3s';
SET LOCAL statement_timeout = '30s';
SET LOCAL idle_in_transaction_session_timeout = '30s';

-- Stop new runtime entry before proving structural rollback is safe.
REVOKE EXECUTE ON FUNCTION agent_credential_private.read_binding(text)
  FROM agent_secret_host;
REVOKE EXECUTE ON FUNCTION agent_credential_private.cas_binding(text,bigint,jsonb)
  FROM agent_secret_host;

DO $rollback_guard$
DECLARE
  v_binding_count bigint;
  v_mapping_count bigint;
BEGIN
  IF pg_catalog.to_regrole('agent_secret_host') IS NULL
      OR pg_catalog.to_regrole('agent_secret_broker') IS NULL
      OR pg_catalog.to_regnamespace('agent_credential_private') IS NULL THEN
    RAISE EXCEPTION 'phase_b_rollback_expected_boundary_missing' USING ERRCODE = '55000';
  END IF;

  IF EXISTS (
    SELECT 1
    FROM pg_catalog.pg_stat_activity AS a
    WHERE a.usename = 'agent_secret_host'
      AND a.pid <> pg_catalog.pg_backend_pid()
  ) THEN
    RAISE EXCEPTION 'phase_b_rollback_active_host_session' USING ERRCODE = '55006';
  END IF;

  SELECT count(*) INTO v_binding_count
  FROM agent_credential_private.bindings;

  SELECT count(*) INTO v_mapping_count
  FROM agent_credential_private.host_bindings;

  IF v_binding_count <> 0 OR v_mapping_count <> 0 THEN
    RAISE EXCEPTION 'phase_b_rollback_nonempty_private_state' USING ERRCODE = '55000';
  END IF;
END
$rollback_guard$;

DROP FUNCTION agent_credential_private.cas_binding(text,bigint,jsonb);
DROP FUNCTION agent_credential_private.read_binding(text);

DROP POLICY broker_binding_access ON agent_credential_private.bindings;
DROP POLICY broker_mapping_select ON agent_credential_private.host_bindings;

DROP TABLE agent_credential_private.host_bindings;
DROP TABLE agent_credential_private.bindings;

-- Remove exact external privileges owned by the broker before dropping the role.
REVOKE EXECUTE ON FUNCTION vault.update_secret(uuid,text,text,text,uuid)
  FROM agent_secret_broker;
REVOKE DELETE ON vault.secrets FROM agent_secret_broker;
REVOKE SELECT ON vault.decrypted_secrets FROM agent_secret_broker;
REVOKE USAGE ON SCHEMA vault FROM agent_secret_broker;
REVOKE EXECUTE ON FUNCTION auth.uid() FROM agent_secret_broker;
REVOKE USAGE ON SCHEMA auth FROM agent_secret_broker;

REVOKE USAGE ON SCHEMA agent_credential_private FROM agent_secret_host;
REVOKE USAGE ON SCHEMA agent_credential_private FROM agent_secret_broker;

DROP SCHEMA agent_credential_private;
DROP ROLE agent_secret_host;
DROP ROLE agent_secret_broker;

COMMIT;
