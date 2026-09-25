-- Synthetic ephemeral CI database only. Never run on a Supabase project.
create role anon nologin;
create role authenticated nologin;
create schema auth;
create table auth.users(id uuid primary key);
create function auth.uid() returns uuid language sql stable as $$
  select nullif(current_setting('request.jwt.claim.sub', true), '')::uuid;
$$;
grant usage on schema auth to authenticated, anon;
grant execute on function auth.uid() to authenticated, anon;
create table public.user_profiles(user_id uuid primary key, role text, plan text);
alter table public.user_profiles enable row level security;
create policy own_profile on public.user_profiles for select to authenticated
  using (user_id = auth.uid());
grant select on public.user_profiles to authenticated;
insert into auth.users values
  ('00000000-0000-0000-0000-000000000001'),
  ('00000000-0000-0000-0000-000000000002'),
  ('00000000-0000-0000-0000-000000000003');
insert into public.user_profiles values
  ('00000000-0000-0000-0000-000000000001', 'owner', 'owner'),
  ('00000000-0000-0000-0000-000000000002', 'owner', 'owner'),
  ('00000000-0000-0000-0000-000000000003', 'member', 'free');

create function pg_temp.expect_error(statement text, expected text)
returns void language plpgsql security invoker as $$
begin
  begin
    execute statement;
  exception when others then
    if sqlstate = expected then return; end if;
    raise;
  end;
  raise exception 'expected SQLSTATE % but statement succeeded: %', expected, statement;
end;
$$;

create function pg_temp.assert_true(value boolean, label text)
returns void language plpgsql as $$
begin
  if value is distinct from true then raise exception 'assertion failed: %', label; end if;
end;
$$;
