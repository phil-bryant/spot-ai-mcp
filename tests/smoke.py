"""Protocol smoke test: drives the server over stdio like an MCP client would.

No network, no API key: only handshake, discovery, listing, and error paths.
Run: python3 tests/smoke.py
"""

import json
import subprocess
import sys

EXPECTED_TOOLS = {
    "list_locations", "list_cameras", "get_camera", "get_camera_count",
    "list_appliances", "get_zones", "get_intelligence", "get_lpr_report",
    "get_live_stream_urls", "spot_api_get",
}

REQUESTS = [
    # Modern client: discovery probe, then a versioned request, then a bad version.
    {"jsonrpc": "2.0", "id": 1, "method": "server/discover",
     "params": {"_meta": {"io.modelcontextprotocol/protocolVersion": "2026-07-28"}}},
    {"jsonrpc": "2.0", "id": 2, "method": "tools/list",
     "params": {"_meta": {"io.modelcontextprotocol/protocolVersion": "2026-07-28"}}},
    {"jsonrpc": "2.0", "id": 3, "method": "tools/list",
     "params": {"_meta": {"io.modelcontextprotocol/protocolVersion": "1900-01-01"}}},
    # Legacy client: initialize handshake with a known and an unknown version.
    {"jsonrpc": "2.0", "id": 4, "method": "initialize",
     "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                "clientInfo": {"name": "smoke", "version": "0"}}},
    {"jsonrpc": "2.0", "method": "notifications/initialized"},
    {"jsonrpc": "2.0", "id": 5, "method": "initialize",
     "params": {"protocolVersion": "1900-01-01", "capabilities": {},
                "clientInfo": {"name": "smoke", "version": "0"}}},
    {"jsonrpc": "2.0", "id": 6, "method": "tools/list"},
    {"jsonrpc": "2.0", "id": 7, "method": "ping"},
    {"jsonrpc": "2.0", "id": 8, "method": "no/such/method"},
]


def main():
    stdin = "".join(json.dumps(r) + "\n" for r in REQUESTS)
    proc = subprocess.run(
        [sys.executable, "-m", "spot_ai_mcp"],
        input=stdin, capture_output=True, text=True, timeout=30,
    )
    assert proc.returncode == 0, f"server exited {proc.returncode}: {proc.stderr}"
    replies = {m["id"]: m for m in map(json.loads, proc.stdout.splitlines())}
    assert len(replies) == 8, f"expected 8 replies, got {len(replies)}"

    discover = replies[1]["result"]
    assert discover["supportedVersions"] == ["2026-07-28"], discover
    assert "tools" in discover["capabilities"], discover
    assert discover["_meta"]["io.modelcontextprotocol/serverInfo"]["name"] == "spot-ai", discover

    tools = {t["name"] for t in replies[2]["result"]["tools"]}
    assert tools == EXPECTED_TOOLS, f"tool mismatch: {tools ^ EXPECTED_TOOLS}"
    for t in replies[2]["result"]["tools"]:
        assert t.get("annotations") == {"readOnlyHint": True}, f"missing readOnlyHint: {t['name']}"

    err = replies[3]["error"]
    assert err["code"] == -32022 and err["data"]["supported"] == ["2026-07-28"], err

    assert replies[4]["result"]["protocolVersion"] == "2025-06-18", replies[4]
    assert replies[5]["result"]["protocolVersion"] == "2025-06-18", replies[5]  # counter-offer, not echo
    assert {t["name"] for t in replies[6]["result"]["tools"]} == EXPECTED_TOOLS
    assert replies[7]["result"] == {}, replies[7]
    assert replies[8]["error"]["code"] == -32601, replies[8]

    print("smoke test passed: 8/8 replies correct")


if __name__ == "__main__":
    main()
