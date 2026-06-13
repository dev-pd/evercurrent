-- Runs once at DB init (before the app connects). The 0014 migration grants
-- privileges + installs RLS policies; this just guarantees the login role
-- exists so the api can connect as the non-superuser app role from cold start.
DO $$ BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'app_rw') THEN
    CREATE ROLE app_rw LOGIN PASSWORD 'app_rw'
      NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;
  END IF;
END $$;
GRANT USAGE ON SCHEMA public TO app_rw;
