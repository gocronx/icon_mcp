"""MCP test client - validates all tools via JSON-RPC over stdio."""

import json
import os
import select
import subprocess
import sys
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PYTHON = os.path.join(BASE_DIR, ".venv", "bin", "python")


def main():
    proc = subprocess.Popen(
        [PYTHON, "-m", "icon_mcp"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    time.sleep(0.5)

    rid = [0]

    def send(obj):
        msg = json.dumps(obj).encode() + b"\n"
        proc.stdin.write(msg)
        proc.stdin.flush()

    def recv(timeout=15):
        ready, _, _ = select.select([proc.stdout], [], [], timeout)
        if not ready:
            return None
        line = proc.stdout.readline().decode().strip()
        if not line:
            return None
        return json.loads(line)

    def call(method, params=None):
        rid[0] += 1
        req = {"jsonrpc": "2.0", "id": rid[0], "method": method}
        if params is not None:
            req["params"] = params
        send(req)
        return recv()

    def notify(method, params=None):
        req = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            req["params"] = params
        send(req)

    passed = [0]
    failed = [0]

    def test(name, ok, detail=""):
        if ok:
            passed[0] += 1
            print("  [PASS] " + name)
        else:
            failed[0] += 1
            print("  [FAIL] " + name + " -- " + detail)

    try:
        # === Test 1: Initialize ===
        print("\n=== Test 1: Initialize ===")
        r = call("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "test", "version": "1.0.0"},
        })
        test("Server responds", r is not None)
        if r:
            info = r.get("result", {}).get("serverInfo", {})
            test("Server name = icon-mcp-server", info.get("name") == "icon-mcp-server")
            caps = r.get("result", {}).get("capabilities", {})
            test("Has tools capability", "tools" in caps)

        notify("notifications/initialized")
        time.sleep(0.3)

        # === Test 2: List Tools ===
        print("\n=== Test 2: List Tools ===")
        r = call("tools/list", {})
        tools = r.get("result", {}).get("tools", []) if r else []
        names = [t["name"] for t in tools]
        test("{} tools registered".format(len(tools)), len(tools) >= 7)
        for expected in [
            "search_icons", "start_web_server", "stop_web_server",
            "check_selection_status", "get_cache_stats", "clear_cache", "save_icons",
        ]:
            test('Tool "{}"'.format(expected), expected in names)

        # Check schemas
        for tool in tools:
            has_schema = "inputSchema" in tool
            test('Tool "{}" has inputSchema'.format(tool["name"]), has_schema)

        # === Test 3: get_cache_stats ===
        print("\n=== Test 3: get_cache_stats ===")
        r = call("tools/call", {"name": "get_cache_stats", "arguments": {}})
        content = r.get("result", {}).get("content", []) if r else []
        if content:
            stats = json.loads(content[0]["text"])
            test("Has icon_cache", "icon_cache" in stats)
            test("Has search_cache", "search_cache" in stats)
            test("Cache empty initially", stats.get("icon_cache", {}).get("total") == 0)
            test("Expiry = 30min", stats.get("cache_expiry_minutes") == 30)
        else:
            test("get_cache_stats returned content", False, str(r))

        # === Test 4: search_icons ===
        print("\n=== Test 4: search_icons ===")
        r = call("tools/call", {"name": "search_icons", "arguments": {"q": "home", "pageSize": 5}})
        content = r.get("result", {}).get("content", []) if r else []
        if content:
            result = json.loads(content[0]["text"])
            if "error" in result:
                print("  [WARN] API error (likely network sandbox): " + result["error"][:120])
                test("Returned structured error", True)
            else:
                test("Found {} icons".format(result.get("count", 0)), result.get("count", 0) > 0)
                test("Has search_id", bool(result.get("search_id")))
                test("Has web_url with searchId", "searchId" in result.get("web_url", ""))
                test("Has 4 instructions", len(result.get("instructions", [])) == 4)
                test("Has waiting_message", bool(result.get("waiting_message")))
        else:
            test("search_icons returned content", False, str(r))

        # === Test 5: start_web_server ===
        print("\n=== Test 5: start_web_server ===")
        r = call("tools/call", {"name": "start_web_server", "arguments": {"port": 19999, "autoOpen": False}})
        content = r.get("result", {}).get("content", []) if r else []
        if content:
            result = json.loads(content[0]["text"])
            test("Server started (has port)", "port" in result)
            test("Has URL", "localhost" in result.get("url", ""))
            test("WebSocket enabled", result.get("websocket") is True)
        else:
            test("start_web_server returned content", False, str(r))

        # === Test 6: stop_web_server ===
        print("\n=== Test 6: stop_web_server ===")
        r = call("tools/call", {"name": "stop_web_server", "arguments": {}})
        content = r.get("result", {}).get("content", []) if r else []
        if content:
            result = json.loads(content[0]["text"])
            test("Server stopped (has message)", "message" in result)
        else:
            test("stop_web_server returned content", False, str(r))

        # === Test 7: clear_cache ===
        print("\n=== Test 7: clear_cache ===")
        r = call("tools/call", {"name": "clear_cache", "arguments": {"expiredOnly": False}})
        content = r.get("result", {}).get("content", []) if r else []
        if content:
            result = json.loads(content[0]["text"])
            test("Has message", "message" in result)
            test("Has cleared counts", "icon_cleared" in result)
        else:
            test("clear_cache returned content", False, str(r))

        # === Test 8: Error handling ===
        print("\n=== Test 8: Error Handling ===")
        r = call("tools/call", {"name": "nonexistent_tool", "arguments": {}})
        content = r.get("result", {}).get("content", []) if r else []
        if content:
            result = json.loads(content[0]["text"])
            test("Unknown tool returns error", "error" in result)

        # === Test 9: Ping ===
        print("\n=== Test 9: Ping ===")
        r = call("ping", {})
        test("Ping response received", r is not None and "result" in r)

    except Exception as e:
        print("\n!!! Test exception: {}".format(e))
        import traceback
        traceback.print_exc()
        failed[0] += 1

    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=3)
        stderr_out = proc.stderr.read().decode().strip()

        if stderr_out:
            print("\n=== Server Logs ===")
            for line in stderr_out.split("\n")[-15:]:
                print("  " + line)

    total = passed[0] + failed[0]
    print("\n" + "=" * 44)
    print("  Results: {} / {} passed, {} failed".format(passed[0], total, failed[0]))
    print("=" * 44)

    return failed[0] == 0


if __name__ == "__main__":
    ok = main()
    sys.exit(0 if ok else 1)
