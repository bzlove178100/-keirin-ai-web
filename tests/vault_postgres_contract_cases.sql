-- Two independent session identities; no real credentials or external provider.
SET SESSION AUTHORIZATION secret_test_host_a;
SELECT pg_temp.assert_true(session_user = 'secret_test_host_a', 'real session identity a');
SELECT pg_temp.assert_true(
  agent_credential_private.read_binding('binding-a') =
  '{"version":0,"state":"ready","refresh_secret":"SYNTHETIC:a0"}'::jsonb, 'initial read');
SELECT pg_temp.expect_error($q$SELECT agent_credential_private.read_binding('binding-b')$q$, '42501');
SELECT pg_temp.expect_error($q$SELECT agent_credential_private.cas_binding('binding-b',0,'ready','SYNTHETIC:stolen')$q$, '42501');
SELECT pg_temp.expect_error('SELECT * FROM synthetic_vault.secrets', '42501');
SELECT pg_temp.expect_error('SELECT * FROM agent_credential_private.bindings', '42501');
SELECT pg_temp.expect_error($q$INSERT INTO agent_credential_private.host_bindings VALUES ('secret_test_host_a','binding-b')$q$, '42501');
SELECT pg_temp.expect_error('SET ROLE secret_test_broker', '42501');
SELECT pg_temp.expect_error('SET ROLE secret_test_host_b', '42501');

SELECT pg_temp.assert_true(
  agent_credential_private.cas_binding('binding-a',0,'refreshing','SYNTHETIC:a1') =
  '{"version":1,"state":"refreshing","refresh_secret":"SYNTHETIC:a1"}'::jsonb, 'atomic success');
SELECT pg_temp.expect_error($q$SELECT agent_credential_private.cas_binding('binding-a',0,'ready','SYNTHETIC:stale')$q$, 'P0002');
SELECT pg_temp.expect_error($q$SELECT agent_credential_private.cas_binding('binding-a',1,'ready','invalid')$q$, '22023');

-- JWT claims cannot substitute for the authenticated database identity.
SET LOCAL request.jwt.claim.sub = '00000000-0000-0000-0000-000000000001';
SELECT pg_temp.expect_error($q$SELECT agent_credential_private.read_binding('binding-a')$q$, '42501');
SET LOCAL request.jwt.claim.sub = '';
RESET SESSION AUTHORIZATION;

-- Inject a failure AFTER the synthetic secret UPDATE, at the metadata UPDATE.
INSERT INTO synthetic_vault.test_faults VALUES ('metadata_update');
SET SESSION AUTHORIZATION secret_test_host_a;
SELECT pg_temp.expect_error($q$SELECT agent_credential_private.cas_binding('binding-a',1,'ready','SYNTHETIC:must-rollback')$q$, 'P0001');
SELECT pg_temp.assert_true(
  agent_credential_private.read_binding('binding-a') =
  '{"version":1,"state":"refreshing","refresh_secret":"SYNTHETIC:a1"}'::jsonb, 'secret and version rollback');
RESET SESSION AUTHORIZATION;
DELETE FROM synthetic_vault.test_faults WHERE operation='metadata_update';

-- Inject failure in the reverse order: metadata revoked, secret DELETE fails.
REVOKE DELETE ON synthetic_vault.secrets FROM secret_test_broker;
SET SESSION AUTHORIZATION secret_test_host_a;
SELECT pg_temp.expect_error($q$SELECT agent_credential_private.cas_binding('binding-a',1,'revoked',NULL)$q$, '42501');
SELECT pg_temp.assert_true(
  agent_credential_private.read_binding('binding-a') =
  '{"version":1,"state":"refreshing","refresh_secret":"SYNTHETIC:a1"}'::jsonb, 'failed revoke rolls back metadata');
RESET SESSION AUTHORIZATION;
GRANT DELETE ON synthetic_vault.secrets TO secret_test_broker;

SET SESSION AUTHORIZATION secret_test_host_b;
SELECT pg_temp.assert_true(session_user = 'secret_test_host_b', 'real session identity b');
SELECT pg_temp.assert_true(
  agent_credential_private.read_binding('binding-b')->>'refresh_secret' = 'SYNTHETIC:b0', 'other binding intact');
SELECT pg_temp.expect_error($q$SELECT agent_credential_private.read_binding('binding-a')$q$, '42501');
RESET SESSION AUTHORIZATION;

-- API identities cannot call private functions, including a BYPASSRLS role.
SET SESSION AUTHORIZATION anon;
SELECT pg_temp.expect_error($q$SELECT agent_credential_private.read_binding('binding-a')$q$, '42501');
RESET SESSION AUTHORIZATION;
SET SESSION AUTHORIZATION authenticated;
SELECT pg_temp.expect_error($q$SELECT agent_credential_private.read_binding('binding-a')$q$, '42501');
RESET SESSION AUTHORIZATION;
SET SESSION AUTHORIZATION service_role;
SELECT pg_temp.expect_error('SELECT * FROM synthetic_vault.secrets', '42501');
SELECT pg_temp.expect_error($q$SELECT agent_credential_private.cas_binding('binding-a',1,'ready','SYNTHETIC:api')$q$, '42501');
RESET SESSION AUTHORIZATION;
SET SESSION AUTHORIZATION authenticator;
SELECT pg_temp.expect_error($q$SELECT agent_credential_private.read_binding('binding-a')$q$, '42501');
RESET SESSION AUTHORIZATION;

SET SESSION AUTHORIZATION secret_test_host_a;
SELECT pg_temp.assert_true(
  agent_credential_private.cas_binding('binding-a',1,'revoked',NULL) =
  '{"version":2,"state":"revoked","refresh_secret":null}'::jsonb, 'revoke clears secret');
SELECT pg_temp.expect_error($q$SELECT agent_credential_private.cas_binding('binding-a',1,'ready','SYNTHETIC:late')$q$, 'P0002');
SELECT pg_temp.expect_error($q$SELECT agent_credential_private.cas_binding('binding-a',2,'ready','SYNTHETIC:resurrect')$q$, '22023');
RESET SESSION AUTHORIZATION;
SELECT pg_temp.assert_true(NOT EXISTS (SELECT 1 FROM synthetic_vault.secrets WHERE id=1), 'revoked secret deleted');

-- Final catalog checks: public execute revoked, runtime roles cannot become broker.
SELECT pg_temp.assert_true(NOT has_function_privilege('anon',
  'agent_credential_private.read_binding(text)', 'EXECUTE'), 'no public function execute');
SELECT pg_temp.assert_true(NOT pg_has_role('secret_test_host_a','secret_test_broker','MEMBER'), 'no broker membership');
