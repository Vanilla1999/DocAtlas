"""One transparent installed MCP transport; exclusive claim prevents reconnect copies.

The registered child uses a held Popen PID; the runner additionally holds pidfds.
Only the installed CLI is executed. Protocol bytes are forwarded unchanged.
"""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time


def main():
    root = Path(sys.argv[1])
    # Claim BEFORE spawn: never start a second CUDA server on client reconnect.
    with (root / 'mcp-started.json').open('x') as stream:
        json.dump({'monotonic_ns': time.monotonic_ns()}, stream)
    child = subprocess.Popen(sys.argv[2:], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE)
    lock = threading.Lock()

    def identity(pid, role):
        raw = Path(f'/proc/{pid}/stat').read_text()
        fields = raw[raw.rfind(')') + 2:].split()
        return dict(role=role, pid=pid, pgid=int(fields[2]), sid=int(fields[3]),
                    start_ticks=int(fields[19]), pid_namespace=os.readlink(f'/proc/{pid}/ns/pid'))

    def log(direction, message):
        with lock, (root / 'stdio-events.jsonl').open('a') as stream:
            stream.write(json.dumps(dict(direction=direction, message=message,
                                         monotonic_ns=time.monotonic_ns(), wall_time_ns=time.time_ns(),
                                         capture_version='wall-v2'), ensure_ascii=False) + '\n')

    def fatal(reason):
        try:
            with (root / 'fatal.json').open('x') as stream:
                json.dump(dict(reason=reason, monotonic_ns=time.monotonic_ns()), stream)
        except FileExistsError:
            pass

    def is_failure(value):
        if not isinstance(value, dict):
            return False
        return (value.get('reason_code') in {'scan_incomplete', 'context_emergency_stop', 'dependency_incomplete'}
                or value.get('hard_stop') is True or value.get('status') in ('error', 'failed'))

    def check_response(value):
        result = value.get('result', {})
        if not isinstance(result, dict):
            return
        if value.get('error') or result.get('isError'):
            fatal('mcp_error')
        packets = [result.get('structuredContent')]
        for item in result.get('content', []):
            if isinstance(item, dict) and item.get('type') == 'text':
                try:
                    packets.append(json.loads(item['text']))
                except (ValueError, KeyError):
                    pass
        if any(is_failure(packet) for packet in packets):
            fatal('technical_retrieval_failure')

    def incoming():
        try:
            for line in sys.stdin.buffer:
                try:
                    value = json.loads(line)
                    log('request', value)
                except ValueError:
                    fatal('invalid_mcp_request')
                child.stdin.write(line)
                child.stdin.flush()
        except BrokenPipeError:
            pass
        finally:
            child.stdin.close()

    def stderr():
        with (root / 'mcp.stderr.log').open('x', encoding='utf-8') as stream:
            for line in child.stderr:
                text = line.decode('utf-8', errors='replace')
                stream.write(text)
                stream.flush()
                # Only server diagnostic stream, never arbitrary source text.
                if any(marker in text.lower() for marker in ('cuda out of memory', 'cuda error: out of memory', 'outofmemoryerror')):
                    fatal('cuda_oom')

    def terminate(*_):
        # No poll/reap elsewhere: child PID remains ours until final wait.
        try:
            child.terminate()
        except ProcessLookupError:
            pass

    try:
        fd = os.open(root / 'mcp-process.json', os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'w') as stream:
            json.dump({'processes': [identity(os.getpid(), 'transport'), identity(child.pid, 'server')]}, stream)
        signal.signal(signal.SIGTERM, terminate)
        threading.Thread(target=incoming, daemon=True).start()
        err = threading.Thread(target=stderr, daemon=True)
        err.start()
        for line in child.stdout:
            try:
                value = json.loads(line)
                log('response', value)  # complete response BEFORE delivery to host
                check_response(value)
            except ValueError:
                fatal('invalid_mcp_response')
            sys.stdout.buffer.write(line)
            sys.stdout.buffer.flush()
    finally:
        terminate()
        try:
            child.wait(timeout=5)
        except subprocess.TimeoutExpired:
            child.kill()
            child.wait(timeout=5)


if __name__ == '__main__':
    main()
