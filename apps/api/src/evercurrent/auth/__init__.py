"""Auth0 integration: JWT verification + FastAPI dependencies.

JWTs from Auth0 are verified against the tenant's public JWKS. The
verified claims include `org_id` (Auth0 organisation ID) and `sub`
(Auth0 user ID). The middleware resolves these to internal Org +
OrgMembership rows and sets the RLS context for the request.
"""
