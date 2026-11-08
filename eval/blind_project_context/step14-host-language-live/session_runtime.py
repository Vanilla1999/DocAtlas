"""Step14 coordinator reusing reviewed Step13 ownership and event classification.

Adds a fatal-file stop and a bounded native capture drain before owned cleanup.
No global service calls; no provider requests are issued from this coordinator.
"""
import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time

BASE = Path(__file__).resolve().parent.parent / 'step13-runtime-token-review/session_runtime.py'
spec = importlib.util.spec_from_file_location('step13_owned_lifecycle', BASE)
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)


def launch_session(*, opencode, location, question, env, output, model, agent, timeout,
                   title, owned_process_files=(), fatal, capture):
    if sys.platform != 'linux' or not hasattr(os, 'WNOWAIT') or not hasattr(signal, 'pidfd_send_signal'):
        raise RuntimeError('Linux pidfds/WNOWAIT required')
    probe = os.pidfd_open(os.getpid())
    os.close(probe)
    for path in owned_process_files:
        info = path.parent.stat()
        if os.path.lexists(path) or info.st_uid != os.getuid() or info.st_mode & 0o022:
            raise RuntimeError('Owned registry must be new in a private owned directory')
    output.mkdir(parents=True, exist_ok=False)
    command = [str(opencode), 'run', '--standalone', '--format', 'json', '--agent', agent,
               '--model', model, '--title', title]
    base.save_new(output / 'launch.json', dict(command=command, cwd=str(location), question=question,
        timeout_seconds=timeout, capture_drain_seconds=10, environment_values_recorded=False,
        automatic_retries=False, owned_process_files=[str(p) for p in owned_process_files]))
    events, capture_errors, observed, registered, registry_errors = [], [], {}, [], {}
    failed = threading.Event()
    threads = []
    process = None
    termination = None
    completed_capture = False
    started = time.monotonic()
    cleanup = dict(no_live_owned_processes=True, leader_reaped=True, not_started=True)

    def reader(pipe, target, parse):
        try:
            with target.open('x') as stream:
                for line in pipe:
                    stream.write(line)
                    stream.flush()
                    if parse and line.strip():
                        try:
                            event = json.loads(line)
                            if not isinstance(event, dict):
                                raise ValueError('not object')
                            events.append(event)
                            if base.event_failure(event):
                                failed.set()
                        except ValueError:
                            capture_errors.append('non_json_cli_stdout')
                            failed.set()
        except Exception as exc:
            capture_errors.append(type(exc).__name__)
            failed.set()
        finally:
            pipe.close()

    def writer(pipe):
        try:
            pipe.write(question)
        except BrokenPipeError:
            pass
        finally:
            try:
                pipe.close()
            except BrokenPipeError:
                pass

    def capture_complete():
        try:
            state = json.loads((capture / 'state.json').read_text())
        except (FileNotFoundError, ValueError):
            return False
        return (state['requests'] > 0 and state['requests'] == state['completed']
                and len(state['usage_ids']) == state['requests'] and state['capture_errors'] == 0)

    try:
        process = subprocess.Popen(command, cwd=location, env=env, stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8', start_new_session=True)
        for values in ((process.stdout, output / 'raw.jsonl', True), (process.stderr, output / 'stderr.log', False)):
            thread = threading.Thread(target=reader, args=values, daemon=True)
            threads.append(thread)
            thread.start()
        thread = threading.Thread(target=writer, args=(process.stdin,), daemon=True)
        threads.append(thread)
        thread.start()
        next_snapshot = 0
        while True:
            now = time.monotonic()
            base._capture_owned_registries(owned_process_files, registered, observed, registry_errors)
            if now >= next_snapshot:
                for member in base._group_members(process.pid):
                    observed[(member['pid'], member['start_ticks'])] = member
                next_snapshot = now + .25
            if registry_errors or fatal.exists() or failed.is_set():
                termination = 'fail_fast'
                break
            if now >= started + timeout:
                termination = 'timeout'
                break
            if os.waitid(os.P_PID, process.pid, os.WEXITED | os.WNOHANG | os.WNOWAIT) is not None:
                # Retain the unreaped leader while allowing asynchronous native
                # response cloning to finish. No sleeps/retries of model work.
                deadline = time.monotonic() + 10
                while not capture_complete() and time.monotonic() < deadline:
                    if fatal.exists() or failed.is_set():
                        break
                    time.sleep(.025)
                completed_capture = capture_complete()
                if not completed_capture:
                    capture_errors.append('provider_response_capture_or_usage_incomplete')
                break
            failed.wait(.025)
    except BaseException:
        termination = 'launcher_exception'
        raise
    finally:
        if process is not None:
            try:
                base._capture_owned_registries(owned_process_files, registered, observed, registry_errors, final=True)
                cleanup = base._cleanup(process, observed, registered, registry_errors)
            except Exception as exc:
                cleanup = dict(no_live_owned_processes=False, leader_reaped=process.returncode is not None,
                               exception_type=type(exc).__name__, boundary='No fallback wider signals')
        for row in registered:
            if row['pidfd'] is not None:
                os.close(row['pidfd'])
        for thread in threads:
            thread.join(timeout=2)
        if any(thread.is_alive() for thread in threads):
            capture_errors.append('stream_did_not_close_after_cleanup')
        code = process.returncode if process else None
        receipt = base.classify_session(events, returncode=code, termination=termination, capture_errors=capture_errors)
        receipt.update(returncode=code, seconds=time.monotonic() - started, cleanup=cleanup,
                       provider_capture_completed_before_cleanup=completed_capture)
        receipt['transport_pass'] = (receipt['transport_pass'] and cleanup['no_live_owned_processes']
                                     and cleanup['leader_reaped'] and completed_capture)
        base.save_new(output / 'receipt.json', receipt)
    return dict(returncode=code, receipt=receipt)
