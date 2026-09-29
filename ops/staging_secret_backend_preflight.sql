-- REVIEW-ONLY / READ-ONLY CATALOG PREFLIGHT.
--
-- This statement never selects from vault.secrets, vault.decrypted_secrets, or any
-- application data table. It reads PostgreSQL catalogs and configuration only.
-- It does not create/alter/drop roles, schemas, objects, grants, passwords or secrets.
-- Catalog output is evidence for a later migration review, not activation approval.
WITH inspected_roles(role_name) AS (
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
    wanted.role_name,
    r.oid,
    r.rolcanlogin,
    r.rolsuper,
    r.rolinherit,
    r.rolcreaterole,
    r.rolcreatedb,
    r.rolreplication,
    r.rolbypassrls
  FROM inspected_roles AS wanted
  LEFT JOIN pg_catalog.pg_roles AS r ON r.rolname = wanted.role_name
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
  WHERE member.rolname IN (SELECT role_name FROM inspected_roles)
     OR granted.rolname IN (SELECT role_name FROM inspected_roles)
),
vault_schema AS (
  SELECT n.oid, n.nspname, pg_catalog.pg_get_userbyid(n.nspowner) AS owner
  FROM pg_catalog.pg_namespace AS n
  WHERE n.nspname = 'vault'
),
private_schema AS (
  SELECT n.oid, n.nspname, pg_catalog.pg_get_userbyid(n.nspowner) AS owner
  FROM pg_catalog.pg_namespace AS n
  WHERE n.nspname = 'agent_credential_private'
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
vault_columns AS (
  SELECT
    c.relname AS relation,
    a.attnum,
    a.attname AS column_name,
    pg_catalog.format_type(a.atttypid, a.atttypmod) AS data_type,
    a.attnotnull AS not_null
  FROM pg_catalog.pg_attribute AS a
  JOIN pg_catalog.pg_class AS c ON c.oid = a.attrelid
  JOIN pg_catalog.pg_namespace AS n ON n.oid = c.relnamespace
  WHERE n.nspname = 'vault'
    AND c.relname IN ('secrets', 'decrypted_secrets')
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
    p.provolatile AS volatility,
    pg_catalog.pg_get_userbyid(p.proowner) AS owner
  FROM pg_catalog.pg_proc AS p
  JOIN pg_catalog.pg_namespace AS n ON n.oid = p.pronamespace
  WHERE n.nspname = 'vault'
),
role_schema_privileges AS (
  SELECT
    r.role_name,
    s.nspname AS schema_name,
    CASE WHEN r.oid IS NULL THEN NULL
         ELSE pg_catalog.has_schema_privilege(r.oid, s.oid, 'USAGE') END AS usage,
    CASE WHEN r.oid IS NULL THEN NULL
         ELSE pg_catalog.has_schema_privilege(r.oid, s.oid, 'CREATE') END AS create_privilege
  FROM role_inventory AS r
  CROSS JOIN (
    SELECT * FROM vault_schema
    UNION ALL
    SELECT * FROM private_schema
  ) AS s
),
role_vault_relation_privileges AS (
  SELECT
    r.role_name,
    v.relname AS relation,
    CASE WHEN r.oid IS NULL THEN NULL
         ELSE pg_catalog.has_table_privilege(r.oid, v.oid, 'SELECT') END AS select_privilege,
    CASE WHEN r.oid IS NULL THEN NULL
         ELSE pg_catalog.has_table_privilege(r.oid, v.oid, 'INSERT') END AS insert_privilege,
    CASE WHEN r.oid IS NULL THEN NULL
         ELSE pg_catalog.has_table_privilege(r.oid, v.oid, 'UPDATE') END AS update_privilege,
    CASE WHEN r.oid IS NULL THEN NULL
         ELSE pg_catalog.has_table_privilege(r.oid, v.oid, 'DELETE') END AS delete_privilege
  FROM role_inventory AS r
  CROSS JOIN vault_relations AS v
),
role_vault_function_privileges AS (
  SELECT
    r.role_name,
    f.proname,
    f.identity_arguments,
    CASE WHEN r.oid IS NULL THEN NULL
         ELSE pg_catalog.has_function_privilege(r.oid, f.oid, 'EXECUTE') END AS execute_privilege
  FROM role_inventory AS r
  CROSS JOIN vault_functions AS f
),
private_objects AS (
  SELECT
    c.relname AS object_name,
    c.relkind,
    pg_catalog.pg_get_userbyid(c.relowner) AS owner,
    c.relrowsecurity,
    c.relforcerowsecurity
  FROM pg_catalog.pg_class AS c
  JOIN pg_catalog.pg_namespace AS n ON n.oid = c.relnamespace
  WHERE n.nspname = 'agent_credential_private'
),
private_functions AS (
  SELECT
    p.proname,
    pg_catalog.pg_get_function_identity_arguments(p.oid) AS identity_arguments,
    p.prosecdef AS security_definer,
    pg_catalog.pg_get_userbyid(p.proowner) AS owner
  FROM pg_catalog.pg_proc AS p
  JOIN pg_catalog.pg_namespace AS n ON n.oid = p.pronamespace
  WHERE n.nspname = 'agent_credential_private'
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
  'session_user', pg_catalog.session_user,
  'current_user', pg_catalog.current_user,
  'in_recovery', pg_catalog.pg_is_in_recovery(),
  'transaction_read_only', pg_catalog.current_setting('transaction_read_only'),
  'postgrest_exposed_schemas_setting', pg_catalog.current_setting('pgrst.db_schemas', true),
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
  'schemas', COALESCE((
    SELECT pg_catalog.jsonb_agg(pg_catalog.to_jsonb(s) ORDER BY s.nspname)
    FROM (
      SELECT * FROM vault_schema
      UNION ALL
      SELECT * FROM private_schema
    ) AS s
  ), '[]'::jsonb),
  'role_schema_privileges', COALESCE((
    SELECT pg_catalog.jsonb_agg(pg_catalog.to_jsonb(p) ORDER BY p.schema_name, p.role_name)
    FROM role_schema_privileges AS p
  ), '[]'::jsonb),
  'vault_relations', COALESCE((
    SELECT pg_catalog.jsonb_agg(pg_catalog.to_jsonb(v) ORDER BY v.relname)
    FROM vault_relations AS v
  ), '[]'::jsonb),
  'vault_columns', COALESCE((
    SELECT pg_catalog.jsonb_agg(pg_catalog.to_jsonb(c) ORDER BY c.relation, c.attnum)
    FROM vault_columns AS c
  ), '[]'::jsonb),
  'role_vault_relation_privileges', COALESCE((
    SELECT pg_catalog.jsonb_agg(pg_catalog.to_jsonb(p) ORDER BY p.relation, p.role_name)
    FROM role_vault_relation_privileges AS p
  ), '[]'::jsonb),
  'vault_functions', COALESCE((
    SELECT pg_catalog.jsonb_agg(pg_catalog.to_jsonb(f) ORDER BY f.proname, f.identity_arguments)
    FROM vault_functions AS f
  ), '[]'::jsonb),
  'role_vault_function_privileges', COALESCE((
    SELECT pg_catalog.jsonb_agg(pg_catalog.to_jsonb(p)
      ORDER BY p.proname, p.identity_arguments, p.role_name)
    FROM role_vault_function_privileges AS p
  ), '[]'::jsonb),
  'existing_private_objects', COALESCE((
    SELECT pg_catalog.jsonb_agg(pg_catalog.to_jsonb(o) ORDER BY o.object_name)
    FROM private_objects AS o
  ), '[]'::jsonb),
  'existing_private_functions', COALESCE((
    SELECT pg_catalog.jsonb_agg(pg_catalog.to_jsonb(f) ORDER BY f.proname, f.identity_arguments)
    FROM private_functions AS f
  ), '[]'::jsonb)
) AS staging_secret_backend_preflight;
