-- REVIEW-ONLY / READ-ONLY DATABASE PREFLIGHT FOR SECRET-CUSTODY C2.
--
-- This statement reads PostgreSQL catalogs/configuration only.
-- It does NOT select from vault.secrets, vault.decrypted_secrets, application tables,
-- provider data, secret values/names/descriptions, or row counts from those relations.
-- It performs no DDL/DML and proves nothing about Data API, SSL-enforcement or network
-- restriction state; those are separate management-plane gates.
WITH target_roles(role_name) AS (
  VALUES
    ('anon'::name),
    ('authenticated'::name),
    ('authenticator'::name),
    ('service_role'::name),
    ('agent_secret_host'::name),
    ('agent_secret_broker'::name)
),
role_inventory AS (
  SELECT
    t.role_name,
    r.oid,
    r.rolcanlogin,
    r.rolsuper,
    r.rolinherit,
    r.rolcreaterole,
    r.rolcreatedb,
    r.rolreplication,
    r.rolbypassrls
  FROM target_roles AS t
  LEFT JOIN pg_catalog.pg_roles AS r ON r.rolname = t.role_name
),
role_memberships AS (
  SELECT
    member.rolname AS member_role,
    granted.rolname AS granted_role,
    am.admin_option,
    am.inherit_option,
    am.set_option
  FROM pg_catalog.pg_auth_members AS am
  JOIN pg_catalog.pg_roles AS member ON member.oid = am.member
  JOIN pg_catalog.pg_roles AS granted ON granted.oid = am.roleid
  WHERE member.rolname IN (SELECT role_name FROM target_roles)
     OR granted.rolname IN (SELECT role_name FROM target_roles)
),
vault_relations AS (
  SELECT
    c.oid,
    c.relname,
    c.relkind,
    c.relrowsecurity,
    c.relforcerowsecurity,
    pg_catalog.pg_get_userbyid(c.relowner) AS owner
  FROM pg_catalog.pg_class AS c
  JOIN pg_catalog.pg_namespace AS n ON n.oid = c.relnamespace
  WHERE n.nspname = 'vault'
    AND c.relname IN ('secrets', 'decrypted_secrets')
),
vault_id_columns AS (
  SELECT
    c.relname AS relation,
    pg_catalog.format_type(a.atttypid, a.atttypmod) AS id_type
  FROM pg_catalog.pg_attribute AS a
  JOIN pg_catalog.pg_class AS c ON c.oid = a.attrelid
  JOIN pg_catalog.pg_namespace AS n ON n.oid = c.relnamespace
  WHERE n.nspname = 'vault'
    AND c.relname IN ('secrets', 'decrypted_secrets')
    AND a.attname = 'id'
    AND a.attnum > 0
    AND NOT a.attisdropped
),
vault_functions AS (
  SELECT
    p.oid,
    p.proname,
    pg_catalog.pg_get_function_identity_arguments(p.oid) AS identity_arguments,
    pg_catalog.pg_get_function_result(p.oid) AS result_type,
    p.prosecdef AS security_definer,
    pg_catalog.pg_get_userbyid(p.proowner) AS owner
  FROM pg_catalog.pg_proc AS p
  JOIN pg_catalog.pg_namespace AS n ON n.oid = p.pronamespace
  WHERE n.nspname = 'vault'
    AND p.proname IN ('create_secret', 'update_secret', '_crypto_aead_det_decrypt')
),
extensions AS (
  SELECT extname, extversion, pg_catalog.pg_get_userbyid(extowner) AS owner
  FROM pg_catalog.pg_extension
  WHERE extname IN ('supabase_vault', 'pgsodium')
)
SELECT pg_catalog.jsonb_build_object(
  'server_version', pg_catalog.current_setting('server_version'),
  'server_version_num', pg_catalog.current_setting('server_version_num'),
  'database', pg_catalog.current_database(),
  'session_user', session_user,
  'current_user', current_user,
  'in_recovery', pg_catalog.pg_is_in_recovery(),
  'transaction_read_only', pg_catalog.current_setting('transaction_read_only'),
  'extensions', COALESCE((
    SELECT pg_catalog.jsonb_agg(pg_catalog.to_jsonb(e) ORDER BY e.extname)
    FROM extensions AS e
  ), '[]'::jsonb),
  'roles', COALESCE((
    SELECT pg_catalog.jsonb_agg(pg_catalog.to_jsonb(r) ORDER BY r.role_name)
    FROM role_inventory AS r
  ), '[]'::jsonb),
  'role_memberships', COALESCE((
    SELECT pg_catalog.jsonb_agg(pg_catalog.to_jsonb(m) ORDER BY m.member_role, m.granted_role)
    FROM role_memberships AS m
  ), '[]'::jsonb),
  'vault_schema', COALESCE((
    SELECT pg_catalog.jsonb_agg(pg_catalog.jsonb_build_object(
      'owner', pg_catalog.pg_get_userbyid(n.nspowner),
      'service_role_usage', pg_catalog.has_schema_privilege('service_role', n.oid, 'USAGE'),
      'anon_usage', pg_catalog.has_schema_privilege('anon', n.oid, 'USAGE'),
      'authenticated_usage', pg_catalog.has_schema_privilege('authenticated', n.oid, 'USAGE')
    ))
    FROM pg_catalog.pg_namespace AS n
    WHERE n.nspname = 'vault'
  ), '[]'::jsonb),
  'vault_relations', COALESCE((
    SELECT pg_catalog.jsonb_agg(pg_catalog.jsonb_build_object(
      'name', v.relname,
      'relkind', v.relkind,
      'rls', v.relrowsecurity,
      'force_rls', v.relforcerowsecurity,
      'owner', v.owner,
      'service_role_select', pg_catalog.has_table_privilege('service_role', v.oid, 'SELECT'),
      'service_role_delete', pg_catalog.has_table_privilege('service_role', v.oid, 'DELETE')
    ) ORDER BY v.relname)
    FROM vault_relations AS v
  ), '[]'::jsonb),
  'vault_id_columns', COALESCE((
    SELECT pg_catalog.jsonb_agg(pg_catalog.to_jsonb(c) ORDER BY c.relation)
    FROM vault_id_columns AS c
  ), '[]'::jsonb),
  'vault_functions', COALESCE((
    SELECT pg_catalog.jsonb_agg(pg_catalog.jsonb_build_object(
      'name', f.proname,
      'identity_arguments', f.identity_arguments,
      'result_type', f.result_type,
      'security_definer', f.security_definer,
      'owner', f.owner,
      'service_role_execute', pg_catalog.has_function_privilege('service_role', f.oid, 'EXECUTE')
    ) ORDER BY f.proname, f.identity_arguments)
    FROM vault_functions AS f
  ), '[]'::jsonb),
  'auth_uid_exists', pg_catalog.to_regprocedure('auth.uid()') IS NOT NULL,
  'agent_secret_host_exists', pg_catalog.to_regrole('agent_secret_host') IS NOT NULL,
  'agent_secret_broker_exists', pg_catalog.to_regrole('agent_secret_broker') IS NOT NULL,
  'agent_credential_private_exists', pg_catalog.to_regnamespace('agent_credential_private') IS NOT NULL
) AS secret_custody_c2_db_preflight;
