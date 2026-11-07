"""Real OpenCode CLI/API question transport, scripted local provider only.

No retrieval or answer quality claim. Captures persisted user messages and the
actual provider-bound request. The frozen question is never rewritten.
"""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hashlib
import json
from pathlib import Path
import subprocess
import threading


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--lane", choices=("cli", "api", "stdin"), action="append")
    args = parser.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    audit = json.loads((Path(__file__).parent / "step10-agent-evaluation/renewed-audit.json").read_text())
    question = audit["question"]["question"]
    requests = []

    def save(name, value):
        (out / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")

    def api(method, path, body=None):
        command = ["opencode", "api", method, path]
        if body is not None:
            command += ["--data", json.dumps(body, ensure_ascii=False)]
        completed = subprocess.run(command, capture_output=True, text=True, check=True, timeout=90)
        return json.loads(completed.stdout) if completed.stdout.strip() else None

    class Provider(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_POST(self):
            request = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            requests.append(request)
            save(f"provider-{len(requests)}.json", request)
            chunks = [{"id": "question-transport", "object": "chat.completion.chunk", "created": 0,
                       "model": "capture", "choices": [{"index": 0, "delta": delta, "finish_reason": reason}]}
                      for delta, reason in (({"role": "assistant", "content": "Transport captured."}, None), ({}, "stop"))]
            data = ("".join("data: " + json.dumps(c) + "\n\n" for c in chunks) + "data: [DONE]\n\n").encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Provider)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    observer = out / "observer"
    observer.mkdir()
    (observer / "index.js").write_text('export default { id: "question-audit-title", async setup(ctx) { await ctx.session.hook("title", e => { e.result = "Question transport audit"; }); } };\n')
    config = {"$schema": "https://opencode.ai/config.json", "snapshots": False,
              "model": "question-audit/capture", "compaction": {"auto": False},
              "plugins": [str(observer)],
              "agents": {"measure": {"mode": "primary", "system": "Transport capture only.",
                                     "permissions": [{"action": "*", "resource": "*", "effect": "deny"}]}},
              "providers": {"question-audit": {"package": "@opencode/ai/providers/openai-compatible",
                  "settings": {"baseURL": f"http://127.0.0.1:{server.server_port}/v1", "apiKey": "local-capture"},
                  "models": {"capture": {"capabilities": {"tools": True, "input": ["text"], "output": ["text"]},
                                         "limit": {"context": 100000, "output": 1000}}}}},
              "mcp": {"servers": {name: {"disabled": True, "type": "local", "command": ["false"]}
                                  for name in ("grounded", "orcaslicer", "blender", "context7", "freecad", "word-server", "sequential-thinking")}}}
    save("opencode.json", config)
    report = {"boundary": "real_OpenCode_transport_scripted_provider_no_DocAtlas_or_Terra",
              "expected_question": question, "expected_sha256": hashlib.sha256(question.encode()).hexdigest(),
              "version": api("get", "/api/info")["version"], "lanes": {}}
    try:
        old = api("get", "/api/session/ses_e4e64fcf0ffeDGGXiZi9TslFbt/message")
        users = [m for m in old["data"] if m.get("type") == "user"]
        save("historical-user-messages.json", users)
        report["historical_user_question_exact"] = any(m["text"] == question for m in users)
        for lane in args.lane or ("cli", "api"):
            session = api("post", "/api/session", {"location": {"directory": str(out)},
                          "title": f"Question transport {lane}", "agent": "measure",
                          "model": {"providerID": "question-audit", "id": "capture"}})["data"]["id"]
            before = len(requests)
            if lane in {"cli", "stdin"}:
                command = ["opencode", "run", "--session", session, "--model", "question-audit/capture",
                           "--agent", "measure", "--format", "json"]
                if lane == "cli":
                    command.append(question)
                save(f"{lane}-argv.json", command)
                completed = subprocess.run(command, cwd=out, capture_output=True, text=True, timeout=90,
                                           input=question if lane == "stdin" else None)
                (out / f"{lane}.jsonl").write_text(completed.stdout)
                (out / f"{lane}.stderr").write_text(completed.stderr)
                completed.check_returncode()
            else:
                api("post", f"/api/session/{session}/prompt", {"text": question})
                api("post", f"/api/experimental/session/{session}/wait", {})
            messages = api("get", f"/api/session/{session}/message")
            save(f"{lane}-messages.json", messages)
            users = [m for m in messages["data"] if m.get("type") == "user"]
            emitted = requests[before:]
            provider_users = [m["content"] for r in emitted for m in r["messages"] if m["role"] == "user"]
            report["lanes"][lane] = {"session": session, "user_texts": [m["text"] for m in users],
                "persisted_exact": len(users) == 1 and users[0]["text"] == question,
                "provider_requests": len(emitted), "provider_user_content": provider_users,
                "provider_exact": len(provider_users) == 1 and provider_users[0] == question}
        save("receipt.json", report)
        save("sha256.json", {str(p.relative_to(out)): hashlib.sha256(p.read_bytes()).hexdigest()
                             for p in sorted(out.rglob("*")) if p.is_file() and p.name != "sha256.json"})
        print(json.dumps(report, ensure_ascii=False, indent=2))
    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()
