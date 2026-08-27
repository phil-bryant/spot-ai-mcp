# spot-ai-mcp

MCP server for the [Spot AI](https://developers.spot.ai) camera / video-intelligence
REST API. Single-file, stdio transport, no dependencies beyond Python 3.

Read-only by design: only GET endpoints are exposed.

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
| `spot_api_get` | Escape hatch: GET any documented `/v1/` or `/v2/` path |

## API key

Resolved lazily on the first API call, in order:

1. `SPOT_AI_API_KEY` environment variable
2. [`1psa`](https://github.com/phil-bryant/1psa): `1psa -f spot.ai api_key`

The key is never written to disk or config. Override the item/field/binary with
`SPOT_AI_OP_ITEM`, `SPOT_AI_OP_FIELD`, `SPOT_AI_OP_BIN`.

The Spot AI key itself must have an **authorization** (role, e.g. Owner, optionally
scoped) added on its settings page in the Spot AI dashboard — a key without a role
returns empty lists from every resource endpoint while `get_camera_count` still works.

## Register with Claude Code

```bash
claude mcp add spot-ai -s user -- python3 /path/to/spot-ai-mcp/server.py
```

## Notes

- Base URL is `https://dev-api.spot.ai`, auth is `Authorization: Bearer <key>`.
- Cloudflare in front of the API rejects Python's default user agent with error 1010;
  the server sends `User-Agent: spot-ai-mcp/<version>`.
- Endpoint index: <https://developers.spot.ai/llms.txt> (append `.md` to any docs URL
  for markdown, including the OpenAPI definition per endpoint).
