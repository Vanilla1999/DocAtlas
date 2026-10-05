"""Exploratory localhost transport only; no provider or scripted reads."""
from contextlib import ExitStack
from copy import deepcopy
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
import hashlib
import importlib.metadata
import json
import os
import secrets
import signal
import subprocess
import sys
import time
import traceback

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
sys.path.insert(0, str(ROOT))
from v2plan.next07_reader_experiment.cases import load_cases
from v2plan.next07_reader_experiment.host import SectionHost
from v2plan.next07_reader_experiment.model import SYSTEM, FINISH, READ, save
from v2plan.next07_reader_experiment.run import hashes, verify_reads
from v2plan.next07_diagnostic_scope import capture_arm
from eval.evidence_quality_v2.runtime import write_project, isolated_service, index_project
from eval.evidence_quality_v2.audit import audit_payload
from docmancer.docs.domain.read_delivery_limits import COMPACT_READ_LIMITS
from jsonschema import Draft202012Validator, ValidationError

COMMANDS = []
SESSIONS = {}
FROZEN = {}


def command(args, artifact):
    result = subprocess.run(args, cwd=ROOT, capture_output=True)
    (OUT / artifact).write_bytes(result.stdout)
    (OUT / (artifact + '.stderr')).write_bytes(result.stderr)
    COMMANDS.append({'argv': args, 'cwd': str(ROOT), 'exit_code': result.returncode,
                     'stdout': artifact, 'stderr': artifact + '.stderr'})
    save(OUT / 'commands.json', COMMANDS)
    if result.returncode:
        raise RuntimeError('metadata command failed: ' + args[0])
    return result.stdout.decode().strip()


def frozen_hashes():
    result = hashes()
    for name in ('pyproject.toml', 'uv.lock', 'v2plan/AGENTS.md',
                 'v2plan/next07_reader_experiment/AGENTS.md',
                 'v2plan/artifacts/next07/reader-review-20261005/REVIEW_RU.md'):
        path = ROOT / name
        if path.is_file():
            result[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    result['EXPLORATORY/bridge.py'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    return result


def check_frozen():
    if frozen_hashes() != FROZEN:
        save(OUT / 'frozen-change.json', {'status': 'STOP_FROZEN_INPUT_CHANGED',
                                         'hashes': frozen_hashes()})
        raise RuntimeError('frozen inputs changed; stop affected measurement')


def tools(row):
    definitions = [FINISH] + ([READ] if row['arm'] == 'B' and row['host'].read_attempts < 2 else [])
    return [{'type': 'function', 'function': deepcopy(d)} for d in definitions]


def persist(row):
    host = row['host']
    verify_reads(host, row['case'].documents)
    if host.context != row['payload']:
        raise RuntimeError('initial packet changed')
    report = {'execution': row['execution'], 'finish': row.get('finish'),
              'quality': 'NOT_GRADED_REVIEW_PENDING', 'exploratory_only': True,
              'read_attempts': host.read_attempts, 'successful_reads': len(host.reads),
              'read_results': deepcopy(host.reads), 'host_events': deepcopy(host.events),
              'visible_evidence': list(deepcopy(host._evidence).values()),
              'initial_context_unchanged': True,
              'citation_errors': row.get('citation_errors', []),
              'finish_contract_errors': row.get('finish_contract_errors', []),
              'reader_metadata': row.get('reader_metadata'),
              'reader_result': row.get('reader_result')}
    save(row['directory'] / 'result.json', report)
    save(row['directory'] / 'transport-events.json', row['events'])


def start(row):
    if row.get('host') is None:
        row['host'] = SectionHost(row['payload'], row['snapshot'], root=str(row['project']),
                                  gateway=row['service'].source_reader.gateway)
        row['started_at'] = time.time()
        row['events'] = []
        row['execution'] = 'NOT_FINISHED'
        value = {'system': SYSTEM, 'question': row['case'].question,
                 'first_view': row['host'].first_view(navigation=row['arm'] == 'B'),
                 'tools': tools(row)}
        row['input'] = value
        save(row['directory'] / 'reader-input.json', value)
        save(row['directory'] / 'lifetime.json', {'started_at_unix': row['started_at'],
             'retention_seconds': 600, 'reset_or_extension': False})
        persist(row)
    return deepcopy(row['input'])


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass  # Do not print case data, raw reader content or opaque tokens.

    def reply(self, status, value):
        data = json.dumps(value, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path == '/health':
            self.reply(200, {'status': 'EXPLORATORY_TRANSPORT_READY', 'initial_native_packets': 10,
                            'model_calls': 0, 'quality': 'NOT_MEASURED'})
            return
        parts = self.path.strip('/').split('/')
        if len(parts) != 2 or parts[0] != 'input' or parts[1] not in SESSIONS:
            self.reply(404, {'error': 'unknown_endpoint'})
            return
        try:
            check_frozen()
            self.reply(200, start(SESSIONS[parts[1]]))
        except Exception:
            save(OUT / 'transport-failure.json', {'traceback': traceback.format_exc()})
            self.reply(409, {'error': 'transport_integrity_failure_stop'})

    def do_POST(self):
        parts = self.path.strip('/').split('/')
        if len(parts) != 2 or parts[0] not in {'read', 'finish'} or parts[1] not in SESSIONS:
            self.reply(404, {'error': 'unknown_endpoint'})
            return
        row = SESSIONS[parts[1]]
        if row.get('host') is None or row['execution'] != 'NOT_FINISHED':
            self.reply(409, {'error': 'input_not_started_or_session_closed'})
            return
        body = self.rfile.read(min(int(self.headers.get('Content-Length', '0')), 2_000_001))
        index = len(row['events'])
        (row['directory'] / f'operator-post-{index}.raw').write_bytes(body)
        try:
            check_frozen()
            data = json.loads(body)
            row['events'].append({'operation': parts[0], 'body': deepcopy(data), 'time': time.time()})
            if parts[0] == 'read':
                Draft202012Validator(READ['parameters']).validate(data)
                if row['arm'] != 'B' or row['host'].read_attempts >= 2:
                    self.reply(409, {'error': 'read_not_permitted'})
                    persist(row)
                    return
                result = row['host'].read_section(data['handle'])
                row['events'][-1]['tool_result'] = deepcopy(result)
                persist(row)
                self.reply(200, result)
            else:
                if not isinstance(data, dict) or set(data) - {'finish', 'reader_result', 'reader_metadata'}:
                    raise ValueError('malformed_finish_envelope')
                Draft202012Validator(FINISH['parameters']).validate(data['finish'])
                finish = data['finish']
                row.update(execution='COMPLETE_EXPLORATORY', finish=finish,
                           reader_result=data.get('reader_result'), reader_metadata=data.get('reader_metadata'),
                           citation_errors=row['host'].citation_errors(finish['citations']), finish_contract_errors=[])
                if finish['status'] in {'answered', 'partial'} and not finish['citations']:
                    row['citation_errors'].append('asserted_answer_without_citation')
                if finish['status'] == 'needs_user_data' and not finish['question_for_user'].strip():
                    row['finish_contract_errors'].append('user_data_status_without_question')
                if finish['status'] == 'answered' and not finish['answer'].strip():
                    row['finish_contract_errors'].append('answered_without_answer')
                persist(row)
                self.reply(200, {'recorded': True, 'execution': row['execution'],
                     'citation_errors': row['citation_errors'], 'finish_contract_errors': row['finish_contract_errors']})
        except (ValueError, KeyError, TypeError, ValidationError):
            row['execution'] = 'INVALID_READER_OR_OPERATOR_ACTION'
            persist(row)
            self.reply(400, {'error': 'invalid_action_recorded_no_repair'})
        except Exception:
            save(row['directory'] / 'failure.json', {'traceback': traceback.format_exc()})
            row['execution'] = 'INVALID_TRANSPORT'
            self.reply(409, {'error': 'transport_integrity_failure_stop'})


def main():
    global FROZEN
    os.chmod(OUT, 0o700)
    os.umask(0o077)
    head = command(['git', 'rev-parse', 'HEAD'], 'head.txt')
    branch = command(['git', 'branch', '--show-current'], 'branch.txt')
    if head != 'f8805a5d696e4ed023fb96f2f7af5f23ccc3e480' or branch != 'next07-feasibility-audit':
        raise RuntimeError('unexpected branch/head')
    command(['git', 'status', '--porcelain=v1', '-uall'], 'dirty-status.txt')
    command(['git', 'diff', '--binary', 'HEAD'], 'dirty.patch')
    untracked = command(['git', 'ls-files', '--others', '--exclude-standard', '-z'], 'untracked-paths.raw')
    save(OUT / 'untracked-hashes.json', {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest()
        for p in untracked.split('\0') if p and (ROOT / p).is_file()
        and not (ROOT / p).is_relative_to(OUT)})
    command([sys.executable, '--version'], 'interpreter.txt')
    dependencies = sorted(({'name': d.metadata['Name'], 'version': d.version}
                          for d in importlib.metadata.distributions()
                          if d.metadata.get('Name')), key=lambda d: d['name'].lower())
    save(OUT / 'dependencies.json', dependencies)
    # Distribution metadata avoids pip-freeze URLs which can contain credentials.
    FROZEN = frozen_hashes()
    save(OUT / 'preflight-hashes.json', FROZEN)
    save(OUT / 'protocol-exploratory.json', {
        'head': head, 'branch': branch, 'python': sys.version, 'executable': sys.executable,
        'mode': 'EXPLORATORY_GENERAL_SUBAGENT_TRANSPORT_ONLY',
        'planned_reader_model': 'openai/gpt-6.1-sol', 'model_calls_by_bridge': 0,
        'deviations': ['Python 3.13.12 rather than published Python 3.12',
                       'ordinary general coding subagents; coding-context contamination acknowledged',
                       'no API provider adapter/credentials; exploratory operator-mediated transport',
                       'no published test suite or scripted native follow-up reads rerun'],
        'published_live_pilot': 'NOT_RUN', 'validated': False,
        'N10': 'EXCLUDED_BY_USER_NOT_RUN_UNCHANGED', 'rollout': 'NOT_AUTHORIZED',
        'arm_contract': {'A': 'unchanged native initial packet only',
                         'B': 'same packet plus unchanged SectionHost navigation and at most two reads'},
        'dependency_metadata': 'installed distribution names/versions, no credential-bearing URLs',
        'scope': '10 native initial C packets; 20 independent arm hosts created lazily; no pre-reads'})
    save(OUT / 'system-and-schemas.json', {'SYSTEM': SYSTEM, 'FINISH': FINISH, 'READ': READ})
    rows, private = [], []
    with ExitStack() as stack:
        cases = load_cases()
        if len(cases) != 10 or len({c.case_id for c in cases}) != 10:
            raise RuntimeError('expected ten frozen cases')
        for case in cases:
            # Opaque corpus directory: case IDs cannot leak through native source paths.
            directory = OUT / 'native' / secrets.token_hex(12)
            project = (directory / 'corpus').resolve()
            write_project(project, case.documents)
            save(directory / 'evaluator-only.json', {'case_id': case.case_id, 'category': case.category,
                 'rubric': case.rubric, 'source_hashes': {p: hashlib.sha256(t.encode()).hexdigest()
                                                       for p, t in case.documents.items()}})
            service, config = stack.enter_context(isolated_service(directory / 'state'))
            save(directory / 'index.json', index_project(service, config, project))
            request = {'question': case.question, 'project_path': str(project), 'scope': 'all'}
            capture = capture_arm(service, request, directory / 'initial', 'C', COMPACT_READ_LIMITS)
            if not capture['valid_execution']:
                raise RuntimeError('invalid initial native execution')
            payload = capture['capture']['public_payload']
            snapshot = capture['trace']['final_snapshot']
            audit = audit_payload(payload, snapshot, project, delivery_limits=COMPACT_READ_LIMITS)
            if audit:
                raise RuntimeError('initial native audit failed')
            rows.append({'case_id': case.case_id, 'status': 'NATIVE_INITIAL_CAPTURED_AUDIT_CLEAN',
                         'audit_errors': audit, 'source_count': len(payload.get('sources', [])),
                         'capture': str((directory / 'initial/capture.json').relative_to(OUT)),
                         'packet_sha256': hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()})
            for arm in ('A', 'B'):
                token = secrets.token_hex(16)
                SESSIONS[token] = {'case': case, 'arm': arm, 'payload': deepcopy(payload),
                     'snapshot': snapshot, 'project': project, 'service': service,
                     'directory': OUT / 'sessions' / token, 'host': None}
                private.append({'case_id': case.case_id, 'arm': arm, 'session': token,
                                'input': '/input/' + token, 'read': '/read/' + token,
                                'finish': '/finish/' + token})
            save(OUT / 'initial-progress.json', rows)
        check_frozen()
        save(OUT / 'initial-capture-exit.json', {'exit_code': 0, 'native_calls': 10,
                                               'audit_clean': 10, 'scripted_reads': 0})
        save(OUT / 'initial-status.json', {'status': 'EXPLORATORY_INITIAL_NATIVE_READY',
             'initial_packets': len(rows), 'audit_clean': len(rows), 'model_sessions': 0,
             'pre_reads': 0, 'published_live': 'NOT_RUN', 'quality': 'NOT_MEASURED', 'rows': rows})
        save(OUT / 'operator-session-map-private.json', private)
        server = HTTPServer(('127.0.0.1', 0), Handler)
        save(OUT / 'bridge-ready.json', {'host': '127.0.0.1', 'port': server.server_port,
             'pid': os.getpid(), 'evidence': str(OUT), 'started_at_unix': time.time(),
             'native_initial_packets': 10, 'pre_reads': 0, 'published_live': 'NOT_RUN'})
        try:
            signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()
            save(OUT / 'postflight-hashes.json', frozen_hashes())


if __name__ == '__main__':
    try:
        main()
        save(OUT / 'bridge-exit.json', {'exit_code': 0})
    except BaseException:
        save(OUT / 'bridge-exit.json', {'exit_code': 1})
        save(OUT / 'bridge-fatal.json', {'traceback': traceback.format_exc()})
        raise
