<!-- mcp-name: io.github.phil-bryant/spot-ai-mcp -->

# spot-ai-mcp

**Unofficial community MCP server for the [Spot AI](https://developers.spot.ai)
camera / video-intelligence REST API. Not affiliated with or endorsed by Spot AI.**

Single-file, stdio transport, no dependencies beyond Python 3.9+.
Read-only by design: it can browse cameras and intelligence data but can never modify
anything in your Spot AI org. Every tool wraps a GET endpoint except
`get_live_stream_urls`, which wraps `POST /v1/cameras/live` — a read-like POST that
only generates a viewing URL. All tools declare the `readOnlyHint: true` MCP annotation.

## Install

```bash
uvx spot-ai-mcp
```

or `pip install spot-ai-mcp`, or run straight from a checkout with
`python3 -m spot_ai_mcp` (no dependencies to install).

Register with Claude Code:

```bash
claude mcp add spot-ai -s user -e SPOT_AI_API_KEY=YOUR_KEY -- uvx spot-ai-mcp
```

## API key

Create a key in the Spot AI dashboard's API settings, then **add an authorization**
(a role, e.g. Owner, optionally scoped) on the key's settings page. A key without a
role returns empty lists from every resource endpoint while `get_camera_count` still
works — that's the tell.

The server resolves the key lazily on the first API call:

1. `SPOT_AI_API_KEY` environment variable — the normal path.
2. Optionally, a secret-helper command, so the key never sits in an env var or config:
   the server runs `$SPOT_AI_OP_BIN -f $SPOT_AI_OP_ITEM $SPOT_AI_OP_FIELD`
   (defaults `1psa -f spot.ai api_key`, per [1psa](https://github.com/phil-bryant/1psa),
   a vault-scoped 1Password service-account CLI). Point these at any command with the
   same flag convention.

The key is never written to disk or config by this server.

## Tools

| Tool | What it does |
|------|--------------|
| `list_locations` | Locations the key can see (paginated) |
| `list_cameras` | Cameras with status, location, IP, MAC (paginated) |
| `get_camera` | One camera by id |
| `get_camera_count` | Number of enabled cameras in the org |
| `list_appliances` | Intelligent Video Recorders (paginated) |
| `get_zones` | Zones defined on a camera |
| `get_intelligence` | Counting / idle / presence events for people, vehicles, or forklifts over a date range |
| `get_lpr_report` | License-plate-recognition report for an LPR camera |
| `get_live_stream_urls` | Live-stream viewing URL for up to 4 cameras |
| `spot_api_get` | Escape hatch: GET any documented `/v1/` or `/v2/` path |

## Notes

- Dual-era MCP server: speaks both the modern per-request protocol
  (`server/discover`, spec 2026-07-28) and the legacy `initialize` handshake
  (2024-11-05 through 2025-06-18), so old and new clients both work.
- Base URL is `https://dev-api.spot.ai`, auth is `Authorization: Bearer <key>`.
- Cloudflare in front of the API rejects Python's default user agent with error 1010;
  the server sends `User-Agent: spot-ai-mcp/<version>`.
- Endpoint index: <https://developers.spot.ai/llms.txt> (append `.md` to any docs URL
  for markdown, including the OpenAPI definition per endpoint).

## License

MIT
