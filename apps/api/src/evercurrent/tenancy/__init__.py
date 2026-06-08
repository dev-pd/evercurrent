"""Postgres row-level security helpers.

`set_org_context(session, org_id)` sets the session-local
`app.current_org_id` variable that RLS policies read. The middleware
calls this at the start of each request; routes don't need to think
about tenant scoping — every SELECT/INSERT/UPDATE/DELETE is filtered
automatically.
"""
