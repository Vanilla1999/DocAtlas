"""Register this explicitly launched MCP process, then exec the real server.

No tool protocol bytes, results, environment values or credentials are recorded.
The PID/start identity survives exec even if OpenCode launches a separate session.
"""
import argparse
import json
import os
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if (not args.registry.is_absolute() or len(command) != 3 or not Path(command[0]).is_absolute()
            or command[1:] != ["mcp", "docs-serve"]):
        parser.error("an absolute new registry and the real doc-atlas mcp docs-serve command are required")
    raw = Path("/proc/self/stat").read_text()
    fields = raw[raw.rfind(")") + 2:].split()
    identity = {"role": "server", "pid": os.getpid(), "pgid": os.getpgrp(), "sid": os.getsid(0),
                "start_ticks": int(fields[19]), "pid_namespace": os.readlink("/proc/self/ns/pid")}
    descriptor = os.open(args.registry, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        json.dump({"processes": [identity]}, stream)
        stream.write("\n")
    os.execvpe(command[0], command, os.environ)


if __name__ == "__main__":
    main()
