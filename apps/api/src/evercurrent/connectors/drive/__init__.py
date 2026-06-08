"""Google Drive connector.

OAuth install + folder picker + push-notification webhook + ingest.
Mirrors the Slack connector's split of responsibilities:

- `install` — OAuth flow (consent URL, code exchange, token encrypt).
- `client` — async Drive API wrapper (httpx).
- `watch` — register + renew files.watch push channels.
- `webhook` — handle Drive's push notifications.
- `schemas` — strict Pydantic models for Drive API payloads.
- `mock` — local-PDF entrypoint used by the demo and tests.
"""
