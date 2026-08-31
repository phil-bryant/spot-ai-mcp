#!/usr/bin/env python3
"""MCP server for the Spot AI camera/intelligence REST API (https://developers.spot.ai).

Read-only: no endpoint that modifies the Spot AI org is exposed. All tools wrap GET
endpoints except get_live_stream_urls, which wraps POST /v1/cameras/live — a read-like
POST that only generates a viewing URL. Stdio transport, no third-party deps.

API key resolution, in order:
  1. SPOT_AI_API_KEY environment variable (recommended)
  2. An optional secret-helper command: SPOT_AI_OP_BIN -f SPOT_AI_OP_ITEM SPOT_AI_OP_FIELD
     (defaults: 1psa -f spot.ai api_key — see https://github.com/phil-bryant/1psa)
The key is fetched lazily on the first API call and cached for the process lifetime.
"""

import json
import os
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

__version__ = "0.3.0"

# Legacy = initialize-handshake revisions we implement; modern = per-request-_meta
# revisions (2026-07-28 and later). This server is dual-era per
# https://modelcontextprotocol.io/specification/2026-07-28/basic/versioning
LEGACY_VERSIONS = ("2025-06-18", "2025-03-26", "2024-11-05")
MODERN_VERSIONS = ("2026-07-28",)

BASE_URL = "https://dev-api.spot.ai"
OP_ITEM = os.environ.get("SPOT_AI_OP_ITEM", "spot.ai")
OP_FIELD = os.environ.get("SPOT_AI_OP_FIELD", "api_key")
OP_BIN = os.environ.get("SPOT_AI_OP_BIN", "1psa")

_api_key = None


def get_api_key():
    global _api_key
    if _api_key:
        return _api_key
    key = os.environ.get("SPOT_AI_API_KEY", "").strip()
    if not key:
        try:
            proc = subprocess.run(
                [OP_BIN, "-f", OP_ITEM, OP_FIELD],
                capture_output=True, text=True, timeout=60,
            )
        except FileNotFoundError:
            raise RuntimeError(
                f"No API key found: set the SPOT_AI_API_KEY environment variable "
                f"(the secret-helper fallback '{OP_BIN}' is not installed)"
            )
        except subprocess.TimeoutExpired:
            raise RuntimeError(f"Timed out reading the key via {OP_BIN}")
        if proc.returncode != 0:
            err = proc.stderr.strip().splitlines()[-1] if proc.stderr.strip() else "unknown error"
            raise RuntimeError(f"Could not read '{OP_FIELD}' from 1Password item '{OP_ITEM}' via {OP_BIN}: {err}")
        key = proc.stdout.strip().strip('"')
    if not key:
        raise RuntimeError("Resolved an empty Spot AI API key")
    _api_key = key
    return key


def api_request(path, query=None, body=None):
    if not path.startswith("/"):
        path = "/" + path
    url = BASE_URL + path
    if query:
        pairs = []
        for k, v in query.items():
            if v is None:
                continue
            if isinstance(v, list):
                pairs.extend((k, str(item)) for item in v)
            else:
                pairs.append((k, str(v)))
        if pairs:
            url += "?" + urllib.parse.urlencode(pairs)
    headers = {
        "Authorization": f"Bearer {get_api_key()}",
        "Accept": "application/json",
        "User-Agent": f"spot-ai-mcp/{__version__}",
    }
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            text = resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        text = e.read().decode("utf-8", "replace")[:2000]
        raise RuntimeError(f"HTTP {e.code} from {path}: {text}")
    try:
        return json.loads(text)
    except ValueError:
        return text


PAGINATION = {
    "limit": {"type": "number", "description": "Max results per page"},
    "cursor": {"type": "string", "description": "Pagination cursor from a previous response's 'next' field"},
}

TOOLS = [
    {
        "name": "list_locations",
        "description": "List locations (id and name) the API key has access to. Paginated: pass the response's 'next' value back as 'cursor' until it is null.",
        "inputSchema": {"type": "object", "properties": dict(PAGINATION)},
    },
    {
        "name": "list_cameras",
        "description": "List cameras for the org (id, name, status, location, IP, MAC, appliance). Paginated via cursor.",
        "inputSchema": {"type": "object", "properties": dict(PAGINATION)},
    },
    {
        "name": "get_camera",
        "description": "Get details for a single camera by id.",
        "inputSchema": {
            "type": "object",
            "properties": {"camera_id": {"type": "number", "description": "Camera id"}},
            "required": ["camera_id"],
        },
    },
    {
        "name": "get_camera_count",
        "description": "Get the number of enabled cameras in the organization.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "list_appliances",
        "description": "List appliances (Intelligent Video Recorders) for the org. Paginated via cursor.",
        "inputSchema": {"type": "object", "properties": dict(PAGINATION)},
    },
    {
        "name": "get_zones",
        "description": "List the zones defined on a camera.",
        "inputSchema": {
            "type": "object",
            "properties": {"camera_id": {"type": "number", "description": "Camera id"}},
            "required": ["camera_id"],
        },
    },
    {
        "name": "get_intelligence",
        "description": "Get intelligence events and summary for a camera: counting, idle, or presence of people, vehicles, or forklifts over a date range.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "camera_id": {"type": "number", "description": "Camera id"},
                "metric": {"type": "string", "enum": ["counting", "idle", "presence"]},
                "entity": {"type": "string", "enum": ["people", "vehicles", "forklifts"]},
                "start_date": {"type": "string", "description": "RFC3339 start of the date range, e.g. 2026-08-01T00:00:00Z"},
                "end_date": {"type": "string", "description": "RFC3339 end of the date range"},
                "start_time": {"type": "string", "description": "Optional daily window start, HH:mm:ss (default 00:00:00)"},
                "end_time": {"type": "string", "description": "Optional daily window end, HH:mm:ss (default 23:59:59)"},
                "threshold": {"type": "number", "description": "Minimum entities in frame to count as an event (default 1)"},
            },
            "required": ["camera_id", "metric", "entity", "start_date", "end_date"],
        },
    },
    {
        "name": "get_lpr_report",
        "description": "Get the license-plate-recognition report for an LPR-enabled camera.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "camera_id": {"type": "number", "description": "Camera id (must be LPR enabled)"},
                "query": {"type": "object", "description": "Optional extra query parameters (e.g. date filters) passed through verbatim"},
            },
            "required": ["camera_id"],
        },
    },
    {
        "name": "get_live_stream_urls",
        "description": "Get a URL to a live stream of up to 4 cameras. Generates a viewing URL for the authenticated caller; modifies nothing.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "camera_ids": {
                    "type": "array",
                    "items": {"type": "number"},
                    "minItems": 1,
                    "maxItems": 4,
                    "description": "Ids of the cameras to create live urls for (1 to 4)",
                },
            },
            "required": ["camera_ids"],
        },
    },
    {
        "name": "spot_api_get",
        "description": "Escape hatch: perform a GET against any documented Spot AI API path (https://developers.spot.ai/llms.txt lists them). Example path: /v1/integrations. Only GET is supported; this server is read-only.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "API path starting with /v1/ or /v2/"},
                "query": {"type": "object", "description": "Query parameters as a flat object"},
            },
            "required": ["path"],
        },
    },
]

# The spec defaults are readOnlyHint=false / destructiveHint=true, so an unannotated
# tool is presumed destructive; every tool here reads without modifying the org.
for _tool in TOOLS:
    _tool["annotations"] = {"readOnlyHint": True}


def call_tool(name, args):
    if name == "list_locations":
        return api_request("/v1/locations", {"limit": args.get("limit"), "cursor": args.get("cursor")})
    if name == "list_cameras":
        return api_request("/v1/cameras", {"limit": args.get("limit"), "cursor": args.get("cursor")})
    if name == "get_camera":
        return api_request(f"/v1/cameras/{int(args['camera_id'])}")
    if name == "get_camera_count":
        return api_request("/v1/cameras/count")
    if name == "list_appliances":
        return api_request("/v1/appliances", {"limit": args.get("limit"), "cursor": args.get("cursor")})
    if name == "get_zones":
        return api_request(f"/v1/cameras/{int(args['camera_id'])}/zones")
    if name == "get_intelligence":
        camera = int(args["camera_id"])
        metric = args["metric"]
        entity = args["entity"]
        if metric not in ("counting", "idle", "presence"):
            raise RuntimeError(f"Unknown metric '{metric}'")
        query = {
            "start_date": args["start_date"],
            "end_date": args["end_date"],
            "start_time": args.get("start_time"),
            "end_time": args.get("end_time"),
            "threshold": args.get("threshold"),
        }
        return api_request(f"/v1/cameras/{camera}/intelligence/{entity}/{metric}", query)
    if name == "get_lpr_report":
        return api_request(f"/v1/lpr/cameras/{int(args['camera_id'])}/report", args.get("query") or {})
    if name == "get_live_stream_urls":
        camera_ids = args["camera_ids"]
        if not isinstance(camera_ids, list) or not 1 <= len(camera_ids) <= 4:
            raise RuntimeError("camera_ids must be a list of 1 to 4 camera ids")
        return api_request("/v1/cameras/live", body={"camera_ids": [int(c) for c in camera_ids]})
    if name == "spot_api_get":
        path = args["path"]
        if not path.lstrip("/").startswith(("v1/", "v2/")):
            raise RuntimeError("Path must start with /v1/ or /v2/")
        return api_request(path, args.get("query") or {})
    raise RuntimeError(f"Unknown tool '{name}'")


def handle(msg):
    method = msg.get("method")
    msg_id = msg.get("id")
    params = msg.get("params", {})

    # Modern (2026-07-28+) requests declare their protocol version per request.
    # Reject versions we don't implement with UnsupportedProtocolVersionError.
    requested = params.get("_meta", {}).get("io.modelcontextprotocol/protocolVersion")
    if requested and requested not in MODERN_VERSIONS + LEGACY_VERSIONS and msg_id is not None:
        return {
            "jsonrpc": "2.0", "id": msg_id,
            "error": {
                "code": -32022,
                "message": "Unsupported protocol version",
                "data": {"supported": list(MODERN_VERSIONS), "requested": requested},
            },
        }

    if method == "server/discover":
        return {
            "jsonrpc": "2.0", "id": msg_id,
            "result": {
                "resultType": "complete",
                "supportedVersions": list(MODERN_VERSIONS),
                "capabilities": {"tools": {}},
                "_meta": {
                    "io.modelcontextprotocol/serverInfo": {"name": "spot-ai", "version": __version__},
                },
            },
        }
    if method == "initialize":
        client_version = params.get("protocolVersion")
        return {
            "jsonrpc": "2.0", "id": msg_id,
            "result": {
                "protocolVersion": client_version if client_version in LEGACY_VERSIONS else LEGACY_VERSIONS[0],
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "spot-ai", "version": __version__},
            },
        }
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": msg_id, "result": {"tools": TOOLS}}
    if method == "tools/call":
        try:
            result = call_tool(params.get("name"), params.get("arguments") or {})
            text = json.dumps(result, indent=2, default=str)
            if len(text) > 100_000:
                text = text[:100_000] + "\n... (truncated)"
            content = {"content": [{"type": "text", "text": text}], "isError": False}
        except Exception as e:
            content = {"content": [{"type": "text", "text": str(e)}], "isError": True}
        return {"jsonrpc": "2.0", "id": msg_id, "result": content}
    if method == "ping":
        return {"jsonrpc": "2.0", "id": msg_id, "result": {}}
    if msg_id is not None:
        return {"jsonrpc": "2.0", "id": msg_id,
                "error": {"code": -32601, "message": f"Method not found: {method}"}}
    return None  # notification


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except ValueError:
            continue
        reply = handle(msg)
        if reply is not None:
            sys.stdout.write(json.dumps(reply) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
