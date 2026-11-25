# Security notes

This is a personal tool, not a multi-user service. Threat model: one tunnel URL plus one token that
must never be made public.

## What protects you

- **Token auth.** Every `/api/*` route requires an `X-Session-Token` header
  (`secrets.token_urlsafe(24)` generated per session by the Colab notebook).
- **ComfyUI is never exposed.** It binds to `127.0.0.1:8188`; only the adapter's port is tunnelled.
- **CORS** is restricted to GitHub Pages origins, not `*`.
- **Uploads**: 25 MB cap, content sniffed by MIME, random server-side filenames — no user-controlled
  paths reach the filesystem.
- **Outputs**: served through a lookup that rejects path traversal (`/api/output/{filename}`).
- **Rate limits** on generation and upload endpoints stop runaway clients hammering the GPU queue.
- **State is on disk** (`STATE_DIR`), so a restarted adapter resumes cleanly.

## Honest limits

- trycloudflare URLs are unguessable but not authenticated at the tunnel layer; anyone with the URL
  still needs the token. Do not post either publicly.
- The token lives in browser localStorage and is sent as a header; use HTTPS URLs only (tunnels and
  GitHub Pages both are).
- Colab runtimes are ephemeral and run on Google's machines — do not upload material you would not
  process in the cloud.

## Secrets

The session token and any other secrets are passed as environment variables to the adapter, never
written into the repository or the notebook output files.
