-- Full synthetic raw-record validation in one test session.
SET SESSION AUTHORIZATION secret_test_host_a;
SELECT pg_temp.assert_true(session_user = 'secret_test_host_a', 'real session identity a');
SELECT pg_temp.assert_true(
  agent_credential_private.read_binding('binding-a') =
  pg_temp.record_a(0, 'ready', 'SYNTHETIC:a0', 0, NULL, NULL, NULL),
  'initial full record'
);

SELECT pg_temp.expect_error(
  $q$SELECT agent_credential_private.read_binding('binding-b')$q$,
  '42501'
);
SELECT pg_temp.expect_error(
  $q$SELECT agent_credential_private.cas_binding(
    'binding-b', 0,
    '{"schema_version":"credential-refresh-secret-record-v1","provider_id":"provider-b","account_id":"account-b","capabilities":["read:two"],"version":1,"state":"ready","refresh_secret":"SYNTHETIC:stolen","refresh_generation":0,"active_attempt_id":null,"last_attempt_id":null,"failure":null}'::jsonb
  )$q$,
  '42501'
);
SELECT pg_temp.expect_error('SELECT * FROM synthetic_vault.secrets', '42501');
SELECT pg_temp.expect_error('SELECT * FROM agent_credential_private.bindings', '42501');
SELECT pg_temp.expect_error(
  $q$INSERT INTO agent_credential_private.host_bindings
      VALUES ('secret_test_host_a','binding-b')$q$,
  '42501'
);
SELECT pg_temp.expect_error('SET ROLE secret_test_broker', '42501');
SELECT pg_temp.expect_error('SET ROLE secret_test_host_b', '42501');

-- The backend accepts only the exact DurableSecretBackend raw-record shape.
SELECT pg_temp.expect_error(
  $q$SELECT agent_credential_private.cas_binding(
    'binding-a', 0,
    pg_temp.record_a(1,'ready','SYNTHETIC:a1',0,NULL,NULL,NULL) || '{"extra":true}'::jsonb
  )$q$,
  '22023'
);
SELECT pg_temp.expect_error(
  $q$SELECT agent_credential_private.cas_binding(
    'binding-a', 0,
    pg_temp.record_a(1,'ready','SYNTHETIC:a1',0,NULL,NULL,NULL) - 'failure'
  )$q$,
  '22023'
);
SELECT pg_temp.expect_error(
  $q$SELECT agent_credential_private.cas_binding(
    'binding-a', 0,
    jsonb_set(
      pg_temp.record_a(1,'ready','SYNTHETIC:a1',0,NULL,NULL,NULL),
      '{provider_id}', '"provider-x"'::jsonb
    )
  )$q$,
  '22023'
);
SELECT pg_temp.expect_error(
  $q$SELECT agent_credential_private.cas_binding(
    'binding-a', 0,
    jsonb_set(
      pg_temp.record_a(1,'ready','SYNTHETIC:a1',0,NULL,NULL,NULL),
      '{capabilities}', '["write:one","read:one"]'::jsonb
    )
  )$q$,
  '22023'
);
SELECT pg_temp.expect_error(
  $q$SELECT agent_credential_private.cas_binding(
    'binding-a', 0,
    jsonb_set(
      pg_temp.record_a(1,'ready','SYNTHETIC:a1',0,NULL,NULL,NULL),
      '{refresh_generation}', 'true'::jsonb
    )
  )$q$,
  '22023'
);
SELECT pg_temp.expect_error(
  $q$SELECT agent_credential_private.cas_binding(
    'binding-a', 0,
    pg_temp.record_a(2,'ready','SYNTHETIC:a1',0,NULL,NULL,NULL)
  )$q$,
  '22023'
);
SELECT pg_temp.expect_error(
  $q$SELECT agent_credential_private.cas_binding(
    'binding-a', 0,
    pg_temp.record_a(1,'refreshing','SYNTHETIC:a0',0,NULL,NULL,NULL)
  )$q$,
  '22023'
);
SELECT pg_temp.expect_error(
  $q$SELECT agent_credential_private.cas_binding(
    'binding-a', 0,
    pg_temp.record_a(1,'ready','SYNTHETIC:a0',0,'attempt-not-allowed',NULL,NULL)
  )$q$,
  '22023'
);
SELECT pg_temp.expect_error(
  $q$SELECT agent_credential_private.cas_binding(
    'binding-a', 0,
    pg_temp.record_a(1,'ready','SYNTHETIC:a0',0,NULL,'bad attempt!',NULL)
  )$q$,
  '22023'
);
SELECT pg_temp.expect_error(
  $q$SELECT agent_credential_private.cas_binding(
    'binding-a', 0,
    pg_temp.record_a(1,'blocked_auth','SYNTHETIC:a0',0,NULL,'attempt-a-1','raw-provider-error')
  )$q$,
  '22023'
);
SELECT pg_temp.expect_error(
  $q$SELECT agent_credential_private.cas_binding(
    'binding-a', 0,
    pg_temp.record_a(1,'revoked','SYNTHETIC:must-clear',0,NULL,NULL,'credential_source_revoked')
  )$q$,
  '22023'
);

SELECT pg_temp.assert_true(
  agent_credential_private.cas_binding(
    'binding-a', 0,
    pg_temp.record_a(1,'refreshing','SYNTHETIC:a0',0,'attempt-a-1',NULL,NULL)
  ) =
  pg_temp.record_a(1,'refreshing','SYNTHETIC:a0',0,'attempt-a-1',NULL,NULL),
  'atomic full-record claim'
);
SELECT pg_temp.expect_error(
  $q$SELECT agent_credential_private.cas_binding(
    'binding-a', 0,
    pg_temp.record_a(1,'refreshing','SYNTHETIC:stale',0,'attempt-stale',NULL,NULL)
  )$q$,
  'P0002'
);
SELECT pg_temp.expect_error(
  $q$SELECT agent_credential_private.cas_binding(
    'binding-a', 1,
    pg_temp.record_a(2,'ready','invalid',1,NULL,'attempt-a-1',NULL)
  )$q$,
  '22023'
);

-- JWT claims cannot substitute for the authenticated database identity.
SET LOCAL request.jwt.claim.sub = '00000000-0000-0000-0000-000000000001';
SELECT pg_temp.expect_error(
  $q$SELECT agent_credential_private.read_binding('binding-a')$q$,
  '42501'
);
SET LOCAL request.jwt.claim.sub = '';
RESET SESSION AUTHORIZATION;

-- Inject a failure AFTER the synthetic secret UPDATE, at the metadata UPDATE.
INSERT INTO synthetic_vault.test_faults VALUES ('metadata_update');
SET SESSION AUTHORIZATION secret_test_host_a;
SELECT pg_temp.expect_error(
  $q$SELECT agent_credential_private.cas_binding(
    'binding-a', 1,
    pg_temp.record_a(2,'ready','SYNTHETIC:must-rollback',1,NULL,'attempt-a-1',NULL)
  )$q$,
  'P0001'
);
SELECT pg_temp.assert_true(
  agent_credential_private.read_binding('binding-a') =
  pg_temp.record_a(1,'refreshing','SYNTHETIC:a0',0,'attempt-a-1',NULL,NULL),
  'secret and full metadata rollback'
);
RESET SESSION AUTHORIZATION;
DELETE FROM synthetic_vault.test_faults WHERE operation = 'metadata_update';

-- Inject failure in the reverse order: metadata revoked, secret DELETE fails.
REVOKE DELETE ON synthetic_vault.secrets FROM secret_test_broker;
SET SESSION AUTHORIZATION secret_test_host_a;
SELECT pg_temp.expect_error(
  $q$SELECT agent_credential_private.cas_binding(
    'binding-a', 1,
    pg_temp.record_a(2,'revoked',NULL,0,NULL,'attempt-a-1','credential_source_revoked')
  )$q$,
  '42501'
);
SELECT pg_temp.assert_true(
  agent_credential_private.read_binding('binding-a') =
  pg_temp.record_a(1,'refreshing','SYNTHETIC:a0',0,'attempt-a-1',NULL,NULL),
  'failed revoke rolls back complete metadata'
);
RESET SESSION AUTHORIZATION;
GRANT DELETE ON synthetic_vault.secrets TO secret_test_broker;

-- A valid blocked-auth record preserves only allowlisted diagnostic metadata.
SET SESSION AUTHORIZATION secret_test_host_a;
SELECT pg_temp.assert_true(
  agent_credential_private.cas_binding(
    'binding-a', 1,
    pg_temp.record_a(
      2,'blocked_auth','SYNTHETIC:a0',0,NULL,'attempt-a-1','refresh_rejected'
    )
  ) =
  pg_temp.record_a(
    2,'blocked_auth','SYNTHETIC:a0',0,NULL,'attempt-a-1','refresh_rejected'
  ),
  'blocked auth full record'
);
RESET SESSION AUTHORIZATION;

SET SESSION AUTHORIZATION secret_test_host_b;
SELECT pg_temp.assert_true(session_user = 'secret_test_host_b', 'real session identity b');
SELECT pg_temp.assert_true(
  agent_credential_private.read_binding('binding-b')->>'refresh_secret' = 'SYNTHETIC:b0',
  'other binding intact'
);
SELECT pg_temp.expect_error(
  $q$SELECT agent_credential_private.read_binding('binding-a')$q$,
  '42501'
);
RESET SESSION AUTHORIZATION;

-- API identities cannot call private functions, including a BYPASSRLS role.
SET SESSION AUTHORIZATION anon;
SELECT pg_temp.expect_error(
  $q$SELECT agent_credential_private.read_binding('binding-a')$q$,
  '42501'
);
RESET SESSION AUTHORIZATION;
SET SESSION AUTHORIZATION authenticated;
SELECT pg_temp.expect_error(
  $q$SELECT agent_credential_private.read_binding('binding-a')$q$,
  '42501'
);
RESET SESSION AUTHORIZATION;
SET SESSION AUTHORIZATION service_role;
SELECT pg_temp.expect_error('SELECT * FROM synthetic_vault.secrets', '42501');
SELECT pg_temp.expect_error(
  $q$SELECT agent_credential_private.cas_binding(
    'binding-a',2,
    '{"schema_version":"credential-refresh-secret-record-v1","provider_id":"provider-a","account_id":"account-a","capabilities":["read:one","write:one"],"version":3,"state":"ready","refresh_secret":"SYNTHETIC:api","refresh_generation":0,"active_attempt_id":null,"last_attempt_id":null,"failure":null}'::jsonb
  )$q$,
  '42501'
);
RESET SESSION AUTHORIZATION;
SET SESSION AUTHORIZATION authenticator;
SELECT pg_temp.expect_error(
  $q$SELECT agent_credential_private.read_binding('binding-a')$q$,
  '42501'
);
RESET SESSION AUTHORIZATION;

SET SESSION AUTHORIZATION secret_test_host_a;
SELECT pg_temp.assert_true(
  agent_credential_private.cas_binding(
    'binding-a', 2,
    pg_temp.record_a(3,'revoked',NULL,0,NULL,'attempt-a-1','credential_source_revoked')
  ) =
  pg_temp.record_a(3,'revoked',NULL,0,NULL,'attempt-a-1','credential_source_revoked'),
  'revoke clears secret with full record'
);
SELECT pg_temp.expect_error(
  $q$SELECT agent_credential_private.cas_binding(
    'binding-a', 2,
    pg_temp.record_a(3,'ready','SYNTHETIC:late',0,NULL,NULL,NULL)
  )$q$,
  'P0002'
);
SELECT pg_temp.expect_error(
  $q$SELECT agent_credential_private.cas_binding(
    'binding-a', 3,
    pg_temp.record_a(4,'ready','SYNTHETIC:resurrect',0,NULL,NULL,NULL)
  )$q$,
  '22023'
);
RESET SESSION AUTHORIZATION;
SELECT pg_temp.assert_true(
  NOT EXISTS (SELECT 1 FROM synthetic_vault.secrets WHERE id = 1),
  'revoked secret deleted'
);

-- Final catalog checks: public execute revoked, runtime roles cannot become broker.
SELECT pg_temp.assert_true(
  NOT has_function_privilege(
    'anon',
    'agent_credential_private.read_binding(text)',
    'EXECUTE'
  ),
  'no public read execute'
);
SELECT pg_temp.assert_true(
  NOT has_function_privilege(
    'anon',
    'agent_credential_private.cas_binding(text,bigint,jsonb)',
    'EXECUTE'
  ),
  'no public cas execute'
);
SELECT pg_temp.assert_true(
  NOT pg_has_role('secret_test_host_a','secret_test_broker','MEMBER'),
  'no broker membership'
);
