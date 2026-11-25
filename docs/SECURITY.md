# Security notes

This is a personal tool, not a multi-user service. The threat model is one tunnel URL plus one
bearer token that must never be made public. There are no accounts, roles or per-user isolation.

## What protects you

- **Token auth.** Every `/api/*` route and `/ws/jobs` requires the session token. The notebook
  generates it with `secrets.token_urlsafe(24)`; the adapter can also generate and persist one if
  `OGAI_SESSION_TOKEN` is unset.
- **ComfyUI is never exposed.** ComfyUI binds to `127.0.0.1:8188`; only the adapter's port is
  tunnelled by `cloudflared`.
- **Uploads are checked.** 25 MB cap, magic-byte sniffing (PNG/JPEG/WebP/GIF only), and sanitised
  server-side filenames. User-controlled paths do not reach the filesystem.
- **Outputs are path-safe.** `GET /api/output/{filename}` resolves inside `OGAI_OUTPUT_DIR` and
  rejects traversal.
- **Rate limiting.** Each token gets 30 authenticated requests per 60 seconds across all
  authenticated endpoints. This is a blunt abuse brake, not a security boundary.
- **State is on disk.** Jobs and settings persist under `OGAI_STATE_DIR` and resume cleanly after
  an adapter restart.
- **`/health` is public.** Anyone with the tunnel URL can see the GPU name, VRAM, queue size,
  capabilities and backend version. It does not expose jobs, prompts, models or outputs.

## How the token is stored and sent

- The browser keeps the token in `sessionStorage`, so it is cleared when the tab closes. The
  backend URL is kept in `localStorage` so you do not retype it.
- Requests use the `X-Session-Token` header. The `?token=` query form is accepted for endpoints
  that need to be loaded by `<img>`/`<video>` tags.
- Query parameters can land in browser history, proxy logs and screenshots. Prefer the header for
  API calls; the studio only uses the query form for output media.
- If the adapter generated the token, it is written to `OGAI_STATE_DIR/runtime.json`. The Colab
  notebook prints its token in cell E's output. Treat exported notebooks, screenshots and terminal
  logs as secrets.

## CORS

The adapter's default is `OGAI_CORS_ORIGINS=*`, which **allows any origin**. That is convenient for
a GitHub Pages fork with an unknown URL, but it is not a meaningful security control. CORS does not
authenticate requests: the token does.

For a long-lived install, pin the origin in the adapter environment:

```bash
export OGAI_CORS_ORIGINS=https://<user>.github.io
```

Use the scheme and host only. Multiple origins can be comma-separated.

## Honest limits

- `trycloudflare.com` URLs are unguessable but not authenticated at the tunnel edge. Anyone who
  obtains the URL still needs the token, but do not post either publicly.
- The token is a bearer credential. There is no per-user revocation and no audit trail beyond the
  job list. Rotating it means restarting the adapter (and therefore the Colab cell).
- Colab runtimes are ephemeral and run on Google's machines. Do not upload material you would not
  process in the cloud.
- Drive mirroring copies outputs and a metadata sidecar (including prompts and parameters) to your
  Google Drive when `save_to_drive` is enabled. Keep that folder private.
- Generated content is subject to the model licences; see [WORKFLOWS.md](WORKFLOWS.md).

## Hardening checklist

- [ ] Set `OGAI_CORS_ORIGINS` to your Pages origin.
- [ ] Use a long random `OGAI_SESSION_TOKEN` (24+ bytes) for any non-Colab deployment.
- [ ] Do not share the tunnel URL or token; rotate by restarting section E.
- [ ] Use HTTPS URLs for both the studio and the backend.
- [ ] Keep `MyDrive/OpenGenerativeAI` private.
- [ ] Avoid uploading sensitive images to a shared or public Colab runtime.
- [ ] Keep tokens, state files, model weights and outputs out of git.

## Reporting a security issue

Open a private GitHub security advisory on the repository rather than a public issue, and include
reproduction steps. Do not include live tunnel URLs or tokens.
