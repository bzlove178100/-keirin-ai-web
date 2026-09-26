-- Read-only catalog inventory. Never reads Vault rows, values, names, keys or counts.
-- Object privileges alone are not an activation decision or an exploitability result.
WITH inspected_roles AS (
  SELECT oid, rolname
  FROM pg_catalog.pg_roles
  WHERE rolname IN ('anon', 'authenticated', 'service_role', 'authenticator')
), vault_objects AS (
  SELECT c.oid, c.relname, n.oid AS schema_oid
  FROM pg_catalog.pg_class AS c
  JOIN pg_catalog.pg_namespace AS n ON n.oid = c.relnamespace
  WHERE n.nspname = 'vault' AND c.relname IN ('secrets', 'decrypted_secrets')
), vault_functions AS (
  SELECT p.oid, p.proname, p.prosecdef, n.oid AS schema_oid
  FROM pg_catalog.pg_proc AS p
  JOIN pg_catalog.pg_namespace AS n ON n.oid = p.pronamespace
  WHERE n.nspname = 'vault'
)
SELECT pg_catalog.jsonb_build_object(
  'server_version', pg_catalog.current_setting('server_version'),
  'extensions', COALESCE((
    SELECT pg_catalog.jsonb_agg(pg_catalog.jsonb_build_object(
      'name', extname, 'version', extversion) ORDER BY extname)
    FROM pg_catalog.pg_extension
    WHERE extname IN ('supabase_vault', 'pgsodium')
  ), '[]'::jsonb),
  'inspected_roles', COALESCE((
    SELECT pg_catalog.jsonb_agg(rolname ORDER BY rolname) FROM inspected_roles
  ), '[]'::jsonb),
  'object_privileges', COALESCE((
    SELECT pg_catalog.jsonb_agg(pg_catalog.jsonb_build_object(
      'object', v.relname, 'role', r.rolname,
      'schema_usage', pg_catalog.has_schema_privilege(r.oid, v.schema_oid, 'USAGE'),
      'select', pg_catalog.has_table_privilege(r.oid, v.oid, 'SELECT')
    ) ORDER BY v.relname, r.rolname)
    FROM vault_objects AS v CROSS JOIN inspected_roles AS r
  ), '[]'::jsonb),
  'function_privileges', COALESCE((
    SELECT pg_catalog.jsonb_agg(pg_catalog.jsonb_build_object(
      'function', v.proname,
      'arguments', pg_catalog.pg_get_function_identity_arguments(v.oid),
      'security_definer', v.prosecdef, 'role', r.rolname,
      'schema_usage', pg_catalog.has_schema_privilege(r.oid, v.schema_oid, 'USAGE'),
      'execute', pg_catalog.has_function_privilege(r.oid, v.oid, 'EXECUTE')
    ) ORDER BY v.proname, v.oid, r.rolname)
    FROM vault_functions AS v CROSS JOIN inspected_roles AS r
  ), '[]'::jsonb)
) AS inventory;
