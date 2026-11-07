"""Real OpenCode V2 formatting probe; scripted local provider, recorded MCP packet.

No answering model is used. The external provider and MCP transport are replay
fixtures; OpenCode's registry, Code Mode, tool formatting and HTTP lowering are real.
Run with the repository Python environment (offline projection tokenizer).
"""
from __future__ import annotations

import argparse
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import subprocess
import sys
import threading
import time
from urllib.parse import urlencode


def compact(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def serve_mcp(packet_path, text_only=False):
    packet = json.loads(Path(packet_path).read_text())
    for line in sys.stdin:
        request = json.loads(line)
        if "id" not in request:
            continue
        method = request["method"]
        if method == "initialize":
            result = {"protocolVersion": request["params"]["protocolVersion"],
                      "capabilities": {"tools": {}},
                      "serverInfo": {"name": "recorded-docatlas-packet", "version": "1"}}
        elif method == "tools/list":
            result = {"tools": [{"name": "get_docs_context", "description": "Replay recorded public packet",
                                 "inputSchema": {"type": "object", "properties": {}}}]}
        elif method == "tools/call":
            result = {"content": [{"type": "text", "text": compact(packet)}],
                      "structuredContent": packet, "isError": False}
            if text_only:
                result.pop("structuredContent")
        elif method == "ping":
            result = {}
        else:
            print(compact({"jsonrpc": "2.0", "id": request["id"],
                           "error": {"code": -32601, "message": "Unsupported replay method"}}), flush=True)
            continue
        print(compact({"jsonrpc": "2.0", "id": request["id"], "result": result}), flush=True)


def api(method, path, body=None):
    command = ["opencode", "api", method, path]
    if body is not None:
        command += ["--data", compact(body)]
    result = subprocess.run(command, text=True, capture_output=True, check=True, timeout=120)
    return json.loads(result.stdout) if result.stdout.strip() else None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mcp", type=Path)
    parser.add_argument("--text-only-mcp", action="store_true", help="Replay current single-TextContent server contract")
    parser.add_argument("--adapter-python", type=Path,
                        help="Absolute candidate Python executable; defaults to the probe interpreter")
    parser.add_argument("--packet", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--large-output", action="store_true", help="Enable the documented 50k-safe host output envelope")
    parser.add_argument("--inflate-model-envelope", action="store_true",
                        help="Diagnostic defect injection before the adapter's final model hook")
    parser.add_argument("--expect-stop", choices=["context_emergency_stop", "client_output_truncated"])
    parser.add_argument("--arm", choices=["codemode_object", "codemode_string", "native_raw", "native_adapter"],
                        default="codemode_object")
    args = parser.parse_args()
    if args.mcp:
        serve_mcp(args.mcp, args.text_only_mcp)
        return
    if not args.packet or not args.output:
        parser.error("--packet and --output required")
    from docmancer.docs.application.projection_tokenizer import projection_token_count
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    packet = json.loads(args.packet.read_text())
    wire = compact(packet)
    (output / "packet.json").write_text(wire)
    mcp_result = {"content": [{"type": "text", "text": wire}], "isError": False}
    if not args.text_only_mcp:
        mcp_result["structuredContent"] = packet
    (output / "mcp-result.json").write_text(compact(mcp_result))
    requests = []
    finished = threading.Event()

    class Provider(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            requests.append(body)
            (output / f"provider-request-{len(requests)}.json").write_text(compact(body))
            has_result = any(m["role"] == "tool" for m in body["messages"])
            if has_result:
                delta = {"role": "assistant", "content": "Formatting capture complete."}
                reason = "stop"
            else:
                if args.arm.startswith("codemode"):
                    code = "const packet = await tools.replay.get_docs_context({}); return "
                    code += "JSON.stringify(packet);" if args.arm == "codemode_string" else "packet;"
                    name, arguments = "execute", {"code": code}
                else:
                    name, arguments = "replay_get_docs_context", {}
                delta = {"role": "assistant", "tool_calls": [{"index": 0, "id": "call_spike",
                         "type": "function", "function": {"name": name, "arguments": compact(arguments)}}]}
                reason = "tool_calls"
            chunks = [{"id": "spike", "object": "chat.completion.chunk", "created": 0,
                       "model": "capture", "choices": [{"index": 0, "delta": delta, "finish_reason": None}]},
                      {"id": "spike", "object": "chat.completion.chunk", "created": 0,
                       "model": "capture", "choices": [{"index": 0, "delta": {}, "finish_reason": reason}]}]
            data = ("".join("data: " + compact(c) + "\n\n" for c in chunks) + "data: [DONE]\n\n").encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            if has_result:
                finished.set()

    server = ThreadingHTTPServer(("127.0.0.1", 0), Provider)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    # Observer records public domain results before provider lowering, no content edits.
    observer = output / "observer"
    observer.mkdir()
    observer_source = '''import { writeFileSync } from "node:fs";
export default { id: "docatlas-formatting-observer", async setup(ctx) {
  await ctx.session.hook("title", e => { e.result = "Formatting spike"; });
  await ctx.tool.hook("execute.after", e => {
    writeFileSync(new URL("../tool-result.json", import.meta.url), JSON.stringify(e));
  });
  await ctx.session.hook("context", e => {
    // INJECT_ENVELOPE
    writeFileSync(new URL("../model-context.json", import.meta.url), JSON.stringify(e));
  });
}};
'''
    if args.inflate_model_envelope:
        observer_source = observer_source.replace("// INJECT_ENVELOPE", '''
    for (const message of e.messages) if (message.role === "tool")
      for (const part of message.content) if (part.name === "replay_get_docs_context" && part.result.type === "text")
        part.result.value += " word".repeat(60000);
''')
    (observer / "index.js").write_text(observer_source)
    config = {"$schema": "https://opencode.ai/config.json", "snapshots": False,
              "model": "docatlas-spike/capture", "compaction": {"auto": False},
              "plugins": [str(observer)],
              "providers": {"docatlas-spike": {"package": "@opencode/ai/providers/openai-compatible",
                  "settings": {"baseURL": f"http://127.0.0.1:{server.server_port}/v1", "apiKey": "local-replay"},
                  "models": {"capture": {"capabilities": {"tools": True, "input": ["text"], "output": ["text"]},
                                          "limit": {"context": 1000000, "output": 1000}}}}},
              "mcp": {"servers": {"replay": {"type": "local", "command": [sys.executable, str(Path(__file__).resolve()),
                        "--mcp", str(output / "packet.json")], "codemode": args.arm.startswith("codemode")}}}}
    if args.arm == "native_adapter":
        adapter = Path(__file__).resolve().parents[2] / "integrations/opencode-v2-compact"
        config["plugins"].append({"package": str(adapter), "options": {
            "tools": ["replay_get_docs_context"],
            "python": str(args.adapter_python.absolute()) if args.adapter_python else sys.executable}})
    if args.large_output:
        config["tool_output"] = {"max_bytes": 6400000, "max_lines": 6400000}
    if args.text_only_mcp:
        config["mcp"]["servers"]["replay"]["command"].append("--text-only-mcp")
    (output / "opencode.json").write_text(compact(config))
    session_id = None
    try:
        created = api("post", "/api/session", {"location": {"directory": str(output)},
                      "title": "DocAtlas formatting spike", "model": {"providerID": "docatlas-spike", "id": "capture"}})
        session_id = created["data"]["id"]
        (output / "session.json").write_text(compact(created))
        for _ in range(60):
            status = api("get", "/api/mcp?" + urlencode({"location[directory]": str(output)}))
            replay = next((s for s in status["data"] if s["name"] == "replay"), None)
            if replay and replay["status"]["status"] == "connected":
                break
            time.sleep(0.5)
        else:
            raise RuntimeError(f"Replay MCP did not connect: {replay}")
        api("post", f"/api/session/{session_id}/prompt", {"text": "Run the deterministic formatting probe."})
        if not finished.wait(90):
            raise RuntimeError("No second provider request; inspect isolated project and session")
        api("post", f"/api/experimental/session/{session_id}/wait", {})
        context = api("get", f"/api/session/{session_id}/context")
        (output / "session-context.json").write_text(compact(context))
        visible = [m["content"] for m in requests[-1]["messages"] if m["role"] == "tool"]
        for index, text in enumerate(visible):
            (output / f"model-visible-{index}.txt").write_text(text)
        receipt = {"arm": args.arm, "opencode": api("get", "/api/info")["version"],
                   "packet_sha256": hashlib.sha256(wire.encode()).hexdigest(),
                   "server_text_tokens": projection_token_count(wire.encode()),
                   "model_visible_tokens": [projection_token_count(t.encode()) for t in visible],
                   "provider_requests": len(requests), "paid_model_calls": 0,
                   "large_output": args.large_output,
                   "text_only_mcp": args.text_only_mcp,
                   "adapter_python": str(args.adapter_python) if args.adapter_python else sys.executable,
                   "inflated_model_envelope": args.inflate_model_envelope,
                   "packet_preserved": len(visible) == 1 and visible[0] == wire,
                   "decoded_packet_preserved": len(visible) == 1 and json.loads(visible[0]) == packet
                       if len(visible) == 1 and visible[0].lstrip().startswith("{") else False,
                   "tool_schema_tokens": projection_token_count(compact(requests[0].get("tools", [])).encode()),
                   "boundary": "actual OpenCode; recorded MCP replay; scripted external provider; no retrieval or answer-quality proof"}
        (output / "receipt.json").write_text(json.dumps(receipt, indent=2))
        if args.expect_stop:
            assert len(visible) == 1
            refusal = json.loads(visible[0])
            assert refusal["reason_code"] == args.expect_stop and refusal["delivered"] is False
            assert "sources" not in refusal and "TAIL_SENTINEL" not in visible[0]
            assert receipt["model_visible_tokens"][0] <= 50000
        else:
            assert receipt["decoded_packet_preserved"], "Packet fidelity failed; see captured provider request"
            if args.arm != "codemode_object":
                assert receipt["packet_preserved"], "Compact text was reserialized or truncated"
        print(json.dumps(receipt, indent=2))
    finally:
        if session_id:
            api("post", f"/api/session/{session_id}/interrupt", {"resume": False})
        server.shutdown()


if __name__ == "__main__":
    main()
